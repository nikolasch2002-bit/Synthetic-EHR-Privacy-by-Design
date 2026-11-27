"""Load and check the generator's config file.

Every model forbids unknown keys, so a misspelt key fails at load time
instead of being silently ignored and replaced by a default.
"""

import datetime as dt
import itertools
import math
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "default.yaml"
MIN_AGE = 18


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _check_age_from(age_from: list[int]) -> None:
    """Bands start at MIN_AGE and rise strictly."""
    if not age_from or age_from[0] != MIN_AGE:
        raise ValueError(f"age bands must start at {MIN_AGE}")
    if any(b <= a for a, b in itertools.pairwise(age_from)):
        raise ValueError("age bands must rise strictly")


class AgeShare(Strict):
    age_from: int
    share: float = Field(gt=0, le=1)


class RatesBySex(Strict):
    """Values by age band and sex; each holds from its age to the next band's."""

    age_from: list[int]
    male: list[float]
    female: list[float]

    @model_validator(mode="after")
    def _shape(self) -> "RatesBySex":
        _check_age_from(self.age_from)
        if not len(self.male) == len(self.female) == len(self.age_from):
            raise ValueError("age_from, male and female must have the same length")
        return self


class Prevalence(RatesBySex):
    @model_validator(mode="after")
    def _range(self) -> "Prevalence":
        if any(not 0 <= v <= 1000 for v in self.male + self.female):
            raise ValueError("prevalence is per 1,000, so between 0 and 1000")
        return self


class Mortality(RatesBySex):
    hazard_ratios: dict[str, float]

    @model_validator(mode="after")
    def _range(self) -> "Mortality":
        if any(not 0 <= v <= 1 for v in self.male + self.female):
            raise ValueError("a yearly chance of dying is between 0 and 1")
        if any(v <= 0 for v in self.hazard_ratios.values()):
            raise ValueError("hazard ratios must be above 0")
        return self


class Condition(Strict):
    icd10: str = Field(pattern=r"^[A-Z]\d{2}(\.\d{1,2})?$")
    department: str
    prevalence_per_1000: Prevalence
    prevalence_scale: float = Field(default=1.0, gt=0, le=1)
    raised_by: dict[str, float]  # earlier condition -> odds ratio


class Range(Strict):
    min: int = Field(ge=0)
    max: int

    @model_validator(mode="after")
    def _order(self) -> "Range":
        if self.max < self.min:
            raise ValueError("max must not be below min")
        return self


class History(Strict):
    start: dt.date
    end: dt.date
    reference_date: dt.date

    @model_validator(mode="after")
    def _order(self) -> "History":
        if not self.start < self.end:
            raise ValueError("history must start before it ends")
        if not self.start <= self.reference_date <= self.end:
            raise ValueError("reference_date must fall inside the history")
        return self


class Outpatient(Strict):
    base_per_year: float = Field(ge=0)
    per_condition_per_year: float = Field(ge=0)
    default_department: str  # for a visit with no condition yet
    clinic_hours: Range  # first and last hour a visit can start
    duration_minutes: Range


class Emergency(Strict):
    department: str
    per_year: float = Field(ge=0)
    heart_failure_factor: float = Field(gt=0)
    duration_hours: Range


class RatesByAge(Strict):
    age_from: list[int]
    rate: list[float]

    @model_validator(mode="after")
    def _shape(self) -> "RatesByAge":
        _check_age_from(self.age_from)
        if len(self.rate) != len(self.age_from):
            raise ValueError("age_from and rate must have the same length")
        return self


class Inpatient(Strict):
    per_year: RatesByAge
    heart_failure_factor: float = Field(gt=0)
    length_of_stay_days: Range


class Visits(Strict):
    outpatient: Outpatient
    emergency: Emergency
    inpatient: Inpatient


# --- Week 2: medicines and labs (docs/clinical-rules.md sections 9 to 11) ---


class Drug(Strict):
    atc: str = Field(pattern=r"^[A-Z]\d{2}[A-Z]{2}\d{2}$")
    drug_class: str
    dose: float = Field(gt=0)
    unit: str
    frequency: str


class TreatmentChoice(Strict):
    drugs: dict[str, float]  # medicine -> chance; at most one is chosen
    unless: list[str] = []  # skipped if already on a medicine of these classes
    after_years: Range | None = None  # started this long after diagnosis

    @model_validator(mode="after")
    def _chances(self) -> "TreatmentChoice":
        if (
            any(p < 0 for p in self.drugs.values())
            or sum(self.drugs.values()) > 1 + 1e-9
        ):
            raise ValueError(
                "a choice's chances must be 0 or more and add up to at most 1"
            )
        return self


class MedicationRules(Strict):
    start_after_diagnosis_days: Range
    prescription_days: int = Field(gt=0)
    yearly_stop_chance: float = Field(ge=0, le=1)
    spironolactone_add_on_per_year: float = Field(ge=0, le=1)
    ace_inhibitor_to_arb_switch: float = Field(ge=0, le=1)
    metformin_stop_below_egfr_30: float = Field(ge=0, le=1)


class LabTest(Strict):
    decimals: int = Field(ge=0)  # as reported; thresholds apply to the rounded value
    loinc: str = Field(pattern=r"^\d{1,7}-\d$")
    unit: str
    ref_low: float | None = None
    ref_high: float | None = None
    female_ref_low: float | None = None  # when women's range differs
    female_ref_high: float | None = None
    limit_low: float
    limit_high: float

    @model_validator(mode="after")
    def _order(self) -> "LabTest":
        if not self.limit_low < self.limit_high:
            raise ValueError("limit_low must be below limit_high")
        refs = (self.ref_low, self.ref_high, self.female_ref_low, self.female_ref_high)
        for value in refs:
            if value is not None and not self.limit_low <= value <= self.limit_high:
                raise ValueError(
                    "a reference limit must lie within the physiological limits"
                )
        return self

    def reference(self, sex: str) -> tuple[float | None, float | None]:
        """The reference range for a man ("M") or a woman ("F")."""
        if sex == "F":
            low = self.ref_low if self.female_ref_low is None else self.female_ref_low
            high = (
                self.ref_high if self.female_ref_high is None else self.female_ref_high
            )
            return low, high
        return self.ref_low, self.ref_high


class FollowUp(Strict):
    chance: float = Field(ge=0, le=1)
    days: Range


class LabRules(Strict):
    outpatient_labs_chance: float = Field(ge=0, le=1)
    result_after_hours: Range
    inr_monitoring_days: int = Field(gt=0)
    tests_at_diabetes_diagnosis: list[str]  # outside a visit, on the day
    potassium_after_raas_start: FollowUp
    alt_after_statin_start: FollowUp


class MeanSd(Strict):
    mean: float
    sd: float = Field(ge=0)


class Line(Strict):
    slope: float
    intercept: float
    sd: float = Field(ge=0)


class FloatRange(Strict):
    min: float
    max: float

    @model_validator(mode="after")
    def _order(self) -> "FloatRange":
        if self.max < self.min:
            raise ValueError("max must not be below min")
        return self


class NtProBnpMedian(Strict):
    no_heart_failure: float = Field(gt=0)
    heart_failure: float = Field(gt=0)


class LabModel(Strict):
    egfr_at_age_30: float
    egfr_drop_per_year_of_age: float
    egfr_sd: float = Field(ge=0)
    egfr_ckd_at_start: FloatRange
    egfr_ckd_at_onset: FloatRange
    egfr_ckd_yearly_drop: FloatRange
    creatinine_cv: float = Field(ge=0)
    potassium_mean: float
    potassium_sd: float = Field(ge=0)
    potassium_test_sd: float = Field(ge=0)
    potassium_per_10_egfr_below_60: float
    potassium_drug_effects: dict[str, float]  # drug class -> mmol/L
    sodium_mean: float
    sodium_test_sd: float = Field(ge=0)
    sodium_diuretic_effect: float
    hba1c_healthy: MeanSd
    hba1c_diabetes: MeanSd
    hba1c_metformin_effect: float
    hba1c_insulin_effect: float
    hba1c_test_sd: float = Field(ge=0)
    hba1c_diagnosis_threshold: float  # diabetes is diagnosed at or above this
    hba1c_rise_before_diagnosis_days: int = Field(gt=0)
    drug_effect_days: int = Field(gt=0)
    glucose_healthy: MeanSd
    glucose_from_hba1c: Line
    ldl_healthy: MeanSd
    ldl_hyperlipidaemia: MeanSd
    ldl_statin_reduction: float = Field(ge=0, lt=1)
    ldl_test_sd: float = Field(ge=0)
    alt_median: float = Field(gt=0)
    alt_log_sd: float = Field(ge=0)
    inr_off_warfarin: MeanSd
    inr_on_warfarin: MeanSd
    nt_probnp_median: NtProBnpMedian
    nt_probnp_log_sd: float = Field(ge=0)


class HyperkalaemiaLogOdds(Strict):
    intercept: float
    egfr_per_10_below_60: float
    potassium_per_mmol_above_4_5: float
    diabetes: float
    age_per_10_years_above_60: float
    combination: float
    loop_or_thiazide: float


class Hyperkalaemia(Strict):
    window_days: int = Field(gt=0)
    threshold: float
    log_odds: HyperkalaemiaLogOdds


class PerTest(Strict):
    chance_per_test: float = Field(ge=0, le=1)
    threshold: float


class AltRise(Strict):
    chance: float = Field(ge=0, le=1)
    times_uln: float = Field(gt=1)


class Interactions(Strict):
    hyperkalaemia_after_raas_start: Hyperkalaemia
    hypokalaemia_on_diuretic: PerTest
    inr_above_4_on_warfarin: PerTest
    alt_after_statin_start: AltRise


# Names the generator's rules refer to directly.
REQUIRED_DRUGS = (
    "metformin",
    "insulin_glargine",
    "spironolactone",
    "losartan",
    "warfarin",
)
REQUIRED_TESTS = ("potassium", "sodium", "creatinine", "egfr", "alt", "inr")


class Config(Strict):
    seed: int
    population: int = Field(gt=0)
    locale: str = Field(pattern=r"^[a-z]{2}_[A-Z]{2}$")
    history: History
    age_mix: list[AgeShare]
    max_age: int
    female_share: float = Field(ge=0, le=1)
    conditions: dict[str, Condition]  # in draw order
    prevalent_onset_years_before: Range
    mortality: Mortality
    departments: list[str]
    clinicians_per_department: int = Field(gt=0)
    visits: Visits
    drugs: dict[str, Drug]
    treatment: dict[str, list[TreatmentChoice]]  # condition -> choices
    medication_rules: MedicationRules
    lab_tests: dict[str, LabTest]
    lab_panels: dict[str, list[str]]  # a condition, or no_condition/emergency/inpatient
    lab_rules: LabRules
    lab_model: LabModel
    interactions: Interactions

    @model_validator(mode="after")
    def _cross_checks(self) -> "Config":
        _check_age_from([a.age_from for a in self.age_mix])
        if self.max_age <= self.age_mix[-1].age_from:
            raise ValueError("max_age must be above the last age band")
        # Shares are rounded to 0.1%, so allow that much rounding error.
        total = sum(a.share for a in self.age_mix)
        if not math.isclose(total, 1.0, abs_tol=0.002):
            raise ValueError(f"age_mix shares must add up to 1, not {total:.3f}")

        names = list(self.conditions)
        for position, (name, condition) in enumerate(self.conditions.items()):
            # Conditions are drawn in order, so only earlier ones can raise a chance.
            earlier = set(names[:position])
            for other, odds_ratio in condition.raised_by.items():
                if other not in earlier:
                    raise ValueError(
                        f"{name} is raised by {other}, which is not drawn before it"
                    )
                if odds_ratio <= 0:
                    raise ValueError(
                        f"odds ratio for {other} in {name} must be above 0"
                    )
            if condition.department not in self.departments:
                raise ValueError(
                    f"{name}'s department {condition.department} is not in departments"
                )

        unknown = set(self.mortality.hazard_ratios) - set(names)
        if unknown:
            raise ValueError(
                f"mortality hazard_ratios name unknown conditions: {sorted(unknown)}"
            )
        if self.visits.emergency.department not in self.departments:
            raise ValueError("the emergency department is not in departments")
        if self.visits.outpatient.default_department not in self.departments:
            raise ValueError("the outpatient default department is not in departments")
        self._check_medicines_and_labs(names)
        return self

    def _check_medicines_and_labs(self, conditions: list[str]) -> None:
        classes = {d.drug_class for d in self.drugs.values()}
        for condition, choices in self.treatment.items():
            if condition not in conditions:
                raise ValueError(f"treatment for unknown condition {condition}")
            for choice in choices:
                if unknown := set(choice.drugs) - set(self.drugs):
                    raise ValueError(
                        f"{condition} treatment names unknown drugs {sorted(unknown)}"
                    )
                if unknown := set(choice.unless) - classes:
                    raise ValueError(
                        f"{condition} treatment names unknown classes {sorted(unknown)}"
                    )
        if unknown := set(self.lab_model.potassium_drug_effects) - classes:
            raise ValueError(
                f"potassium_drug_effects names unknown classes {sorted(unknown)}"
            )
        needed = {*conditions, "no_condition", "emergency", "inpatient"}
        if missing := needed - set(self.lab_panels):
            raise ValueError(f"lab_panels is missing {sorted(missing)}")
        if unknown := set(self.lab_rules.tests_at_diabetes_diagnosis) - set(
            self.lab_tests
        ):
            raise ValueError(
                f"tests_at_diabetes_diagnosis names unknown tests {sorted(unknown)}"
            )
        for panel, tests in self.lab_panels.items():
            if unknown := set(tests) - set(self.lab_tests):
                raise ValueError(
                    f"lab panel {panel} names unknown tests {sorted(unknown)}"
                )
        if missing := set(REQUIRED_DRUGS) - set(self.drugs):
            raise ValueError(f"drugs must include {sorted(missing)}")
        if missing := set(REQUIRED_TESTS) - set(self.lab_tests):
            raise ValueError(f"lab_tests must include {sorted(missing)}")


def load_config(path: Path = DEFAULT_CONFIG) -> Config:
    """Read a YAML config file and check it; raises on any error."""
    with open(path, encoding="utf-8") as f:
        return Config.model_validate(yaml.safe_load(f))
