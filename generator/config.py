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
        return self


def load_config(path: Path = DEFAULT_CONFIG) -> Config:
    """Read a YAML config file and check it; raises on any error."""
    with open(path, encoding="utf-8") as f:
        return Config.model_validate(yaml.safe_load(f))
