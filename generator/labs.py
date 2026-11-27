"""Lab orders and results, with the five drug-lab interactions planted.

The rules are in docs/clinical-rules.md, sections 10 and 11. Tests are
ordered at visits (a panel by what the visit is for), as follow-ups after a
medicine starts, and every four weeks on warfarin. Values come from each
patient's own levels, moved by their conditions and medicines. On top, the
interactions are planted at known rates, so the analysis has a right answer:

1. Hyperkalaemia after a RAAS-inhibitor start: decided once per start, from
   a logistic formula whose log-odds are in the config. If it happens, every
   potassium measured in the 30 days after is 5.5 or more; if not, none is.
2. Hypokalaemia on a loop or thiazide diuretic: each potassium, with a chance.
3. INR above 4 on warfarin: each INR, with a chance.
4. Metformin continued with eGFR below 30: decided at the first eGFR result
   below 30 during a metformin therapy. Draw medicine orders after the labs:
   `draw` may stop metformin early in the plan it is given.
5. ALT above 3 x the upper limit after a statin starts: once per start.
"""

import datetime as dt
import math
from dataclasses import dataclass

from generator.conditions import ClinicalHistory, age_years, expit
from generator.config import Config
from generator.kidney import KidneyCourse, ckd_epi_2021, creatinine_for_egfr
from generator.medications import DrugStart, TherapyPlan, new_starts, orders_for
from generator.patients import Patient
from generator.streams import Part, patient_rng
from generator.visits import EMERGENCY, INPATIENT, Encounter, EncounterDiagnosis

LAB_ORDERS_PER_PATIENT_MAX = 100_000
STATIN_WATCH_DAYS = 84
METFORMIN_EGFR_LIMIT = 30  # metformin is contraindicated below this eGFR  # an ALT rise after a statin start shows within 12 weeks
MAX_REDRAWS = 50


@dataclass(frozen=True)
class LabResult:
    lab_order_id: int
    patient_id: int
    encounter_id: int | None  # None: a follow-up or monitoring test outside a visit
    test: str
    loinc: str
    ordered_at: dt.datetime
    value: float
    unit: str
    ref_low: float | None
    ref_high: float | None
    resulted_at: dt.datetime


@dataclass(frozen=True)
class HyperkalaemiaStart:
    """A RAAS-inhibitor start and the planted outcome, with what decided it."""

    start: DrugStart
    chance: float
    event: bool


@dataclass
class _Group:
    """Tests ordered together at one moment."""

    at: dt.datetime
    tests: list[str]
    encounter_id: int | None


def hyperkalaemia_log_odds(
    config: Config, egfr: float, potassium: float, diabetes: bool, age: float,
    combination: bool, diuretic: bool,
) -> float:  # fmt: skip
    """The planted formula (spec, "Prediction model"): the model should recover it."""
    c = config.interactions.hyperkalaemia_after_raas_start.log_odds
    return (
        c.intercept
        + c.egfr_per_10_below_60 * max(0.0, 60 - egfr) / 10
        + c.potassium_per_mmol_above_4_5 * (potassium - 4.5)
        + c.diabetes * diabetes
        + c.age_per_10_years_above_60 * (age - 60) / 10
        + c.combination * combination
        + c.loop_or_thiazide * diuretic
    )


class LabMaker:
    def __init__(self, config: Config):
        self.config = config
        # Panel tests: creatinine before eGFR, because eGFR is computed from it.
        self.order = {name: i for i, name in enumerate(config.lab_tests)}
        self.order["egfr"] = self.order["creatinine"] + 0.5

    def _panel(self, name: str) -> list[str]:
        return sorted(self.config.lab_panels[name], key=self.order.__getitem__)

    def draw(
        self, patient: Patient, history: ClinicalHistory, kidney: KidneyCourse,
        plan: TherapyPlan, encounters: list[Encounter], diagnoses: list[EncounterDiagnosis],
    ) -> tuple[list[LabResult], list[HyperkalaemiaStart]]:  # fmt: skip
        config = self.config
        rules, model = config.lab_rules, config.lab_model
        rng = patient_rng(config.seed, patient.patient_id, Part.LABS)
        last = min(history.death_date or config.history.end, config.history.end)
        onsets = {r.condition: r.onset for r in history.conditions}
        condition_of_code = {c.icd10: name for name, c in config.conditions.items()}

        # The patient's own levels, drawn once.
        own = {
            "potassium": rng.normal(model.potassium_mean, model.potassium_sd),
            "hba1c_healthy": rng.normal(
                model.hba1c_healthy.mean, model.hba1c_healthy.sd
            ),
            "hba1c_diabetes": rng.normal(
                model.hba1c_diabetes.mean, model.hba1c_diabetes.sd
            ),
            "glucose_healthy": rng.normal(
                model.glucose_healthy.mean, model.glucose_healthy.sd
            ),
            "ldl_healthy": rng.normal(model.ldl_healthy.mean, model.ldl_healthy.sd),
            "ldl_high": rng.normal(
                model.ldl_hyperlipidaemia.mean, model.ldl_hyperlipidaemia.sd
            ),
        }

        # --- Which tests, when ---
        groups: list[_Group] = []
        primary = {d.encounter_id: d.icd10 for d in diagnoses if d.is_primary}
        for e in encounters:
            if e.encounter_type in (EMERGENCY, INPATIENT):
                panel = e.encounter_type
            elif rng.random() < rules.outpatient_labs_chance:
                panel = condition_of_code.get(
                    primary.get(e.encounter_id), "no_condition"
                )
            else:
                continue
            groups.append(_Group(e.start, self._panel(panel), e.encounter_id))

        def morning(day: dt.date) -> dt.datetime:
            minutes = int(rng.integers(8 * 60, 11 * 60))
            return dt.datetime.combine(day, dt.time()) + dt.timedelta(minutes=minutes)

        orders = orders_for(config, patient, plan)
        raas_starts = new_starts(config, orders)
        statin_starts = new_starts(config, orders, classes=("statin",))
        for s in raas_starts:
            follow = rules.potassium_after_raas_start
            if rng.random() < follow.chance:
                day = s.day + dt.timedelta(
                    days=int(rng.integers(follow.days.min, follow.days.max + 1))
                )
                if day <= last:
                    groups.append(
                        _Group(
                            morning(day),
                            self._panel_of(["potassium", "creatinine", "egfr"]),
                            None,
                        )
                    )
        # The tests that diagnose diabetes, on the day it is diagnosed.
        diabetes_onset = onsets.get("type2_diabetes")
        if (
            diabetes_onset is not None
            and config.history.start <= diabetes_onset <= last
        ):
            tests = self._panel_of(rules.tests_at_diabetes_diagnosis)
            groups.append(_Group(morning(diabetes_onset), tests, None))
        for s in statin_starts:
            follow = rules.alt_after_statin_start
            if rng.random() < follow.chance:
                day = s.day + dt.timedelta(
                    days=int(rng.integers(follow.days.min, follow.days.max + 1))
                )
                if day <= last:
                    groups.append(_Group(morning(day), ["alt"], None))
        for t in plan.therapies:
            if config.drugs[t.drug].drug_class == "vka":
                day = t.start + dt.timedelta(days=7)
                while day <= min(t.stop, last):
                    groups.append(_Group(morning(day), ["inr"], None))
                    day += dt.timedelta(days=rules.inr_monitoring_days)
        groups.sort(key=lambda g: (g.at, g.encounter_id or 0))

        # The ALT rise is decided once per statin start.
        alt_rise = {
            s.day: rng.random() < config.interactions.alt_after_statin_start.chance
            for s in statin_starts
        }

        # --- Values, in time order, so a start's outcome uses earlier results ---
        decided: list[HyperkalaemiaStart] = []
        pending = list(raas_starts)
        latest: dict[str, tuple[dt.date, float]] = {}  # test -> (day, rounded value)
        metformin_decided: set[dt.date] = set()  # therapies (by start) already decided
        results: list[LabResult] = []

        def decide(start: DrugStart) -> HyperkalaemiaStart:
            """Plant the outcome from what is known before the start day."""
            day = start.day
            age = age_years(patient.birth_date, day)

            def recent(test: str, fallback: float) -> float:
                # The most recent result in the 365 days before; the true level if none.
                if test in latest and 0 < (day - latest[test][0]).days <= 365:
                    return latest[test][1]
                return fallback

            on = plan.classes_on(day)
            log_odds = hyperkalaemia_log_odds(
                config,
                egfr=recent("egfr", kidney.egfr(day)),
                potassium=recent(
                    "potassium", self._potassium_level(own, kidney, plan, day)
                ),
                diabetes=onsets.get("type2_diabetes", dt.date.max) <= day,
                age=age,
                combination=bool(on & {"ace_inhibitor", "arb"}) and "mra" in on,
                diuretic=bool(on & {"loop_diuretic", "thiazide"}),
            )
            chance = expit(log_odds)
            return HyperkalaemiaStart(start, chance, bool(rng.random() < chance))

        for group in groups:
            while pending and pending[0].day <= group.at.date():
                decided.append(decide(pending.pop(0)))
            day = group.at.date()
            age = age_years(patient.birth_date, day)
            creatinine = None
            for test in group.tests:
                spec = config.lab_tests[test]
                if test == "creatinine" or (test == "egfr" and creatinine is None):
                    true_creatinine = creatinine_for_egfr(
                        kidney.egfr(day), age, patient.sex
                    )
                    creatinine = true_creatinine * math.exp(
                        rng.normal(0, model.creatinine_cv)
                    )
                if test == "creatinine":
                    value = creatinine
                elif test == "egfr":
                    value = ckd_epi_2021(creatinine, age, patient.sex)
                else:
                    value = self._value(
                        rng,
                        test,
                        own,
                        kidney,
                        plan,
                        onsets,
                        day,
                        decided,
                        alt_rise,
                        patient.sex,
                    )
                value = round(
                    min(max(value, spec.limit_low), spec.limit_high), spec.decimals
                )
                if spec.decimals == 0:
                    value = int(value)
                low, high = spec.reference(patient.sex)
                hours = rules.result_after_hours
                resulted = group.at + dt.timedelta(
                    minutes=int(rng.integers(hours.min * 60, hours.max * 60 + 1))
                )
                order_id = (
                    patient.patient_id * LAB_ORDERS_PER_PATIENT_MAX + len(results) + 1
                )
                results.append(
                    LabResult(
                        order_id,
                        patient.patient_id,
                        group.encounter_id,
                        test,
                        spec.loinc,
                        group.at,
                        value,
                        spec.unit,
                        low,
                        high,
                        resulted,
                    )
                )
                latest[test] = (day, float(value))
                if test == "egfr" and value < METFORMIN_EGFR_LIMIT:
                    self._metformin_rule(rng, plan, day, metformin_decided)
        while pending:
            decided.append(decide(pending.pop(0)))
        if len(results) >= LAB_ORDERS_PER_PATIENT_MAX:
            raise RuntimeError(f"patient {patient.patient_id} has too many lab orders")
        return results, decided

    def _metformin_rule(
        self, rng, plan: TherapyPlan, day: dt.date, decided: set
    ) -> None:
        """Interaction 4: at the first eGFR result below 30 during a metformin
        therapy, most patients stop it within 30 days; the rest continue.
        Decided on the result, as a doctor would, not on the true value."""
        therapy = next(
            (
                t
                for t in plan.therapies
                if t.drug == "metformin" and t.start <= day <= t.stop
            ),
            None,
        )
        if therapy is None or therapy.start in decided:
            return
        decided.add(therapy.start)
        if rng.random() < self.config.medication_rules.metformin_stop_below_egfr_30:
            plan.stop_early(therapy, day + dt.timedelta(days=int(rng.integers(0, 31))))

    def _panel_of(self, tests: list[str]) -> list[str]:
        return sorted(tests, key=self.order.__getitem__)

    def _potassium_level(
        self, own, kidney: KidneyCourse, plan: TherapyPlan, day: dt.date
    ) -> float:
        """The patient's true potassium on `day`, before test-to-test noise."""
        model = self.config.lab_model
        level = own["potassium"]
        level += (
            model.potassium_per_10_egfr_below_60 * max(0.0, 60 - kidney.egfr(day)) / 10
        )
        level += sum(
            model.potassium_drug_effects.get(c, 0.0) for c in plan.classes_on(day)
        )
        return level

    def _value(
        self, rng, test, own, kidney, plan, onsets, day, decided, alt_rise, sex
    ) -> float:
        config, model = self.config, self.config.lab_model
        classes = plan.classes_on(day)
        spec = config.lab_tests[test]

        def ramp(drug: str) -> float:
            """0 to 1: how much of a medicine's effect is reached on `day`."""
            since = plan.started_on(drug, day)
            return (
                0.0
                if since is None
                else min((day - since).days / model.drug_effect_days, 1.0)
            )

        def rounded(v: float) -> float:
            return round(min(max(v, spec.limit_low), spec.limit_high), spec.decimals)

        def redraw(draw, keep, fallback: float) -> float:
            """Draw until `keep(rounded value)`, as thresholds apply to the reported value.

            After MAX_REDRAWS misses (a level far beyond the threshold), the
            fallback, which `keep` accepts, so a planted rate is never broken.
            """
            for _ in range(MAX_REDRAWS):
                v = draw()
                if keep(rounded(v)):
                    return v
            return fallback

        if test == "potassium":
            hk = config.interactions.hyperkalaemia_after_raas_start
            for d in decided:
                if 0 < (day - d.start.day).days <= hk.window_days:
                    if d.event:
                        return rng.uniform(hk.threshold, hk.threshold + 1.0)
                    level = self._potassium_level(own, kidney, plan, day)
                    return redraw(
                        lambda level=level: rng.normal(level, model.potassium_test_sd),
                        lambda v: v < hk.threshold,
                        fallback=hk.threshold - 0.1,
                    )
            level = self._potassium_level(own, kidney, plan, day)
            low = config.interactions.hypokalaemia_on_diuretic
            if classes & {"loop_diuretic", "thiazide"}:
                if rng.random() < low.chance_per_test:
                    return rng.uniform(low.threshold - 0.6, low.threshold - 0.06)
                return redraw(
                    lambda: rng.normal(level, model.potassium_test_sd),
                    lambda v: v >= low.threshold,
                    fallback=low.threshold,
                )
            return rng.normal(level, model.potassium_test_sd)

        if test == "sodium":
            effect = (
                model.sodium_diuretic_effect
                if classes & {"loop_diuretic", "thiazide"}
                else 0.0
            )
            return rng.normal(model.sodium_mean + effect, model.sodium_test_sd)

        diabetes_onset = onsets.get("type2_diabetes")
        if test == "hba1c":
            hba1c = self._hba1c(own, diabetes_onset, day, ramp)
            return hba1c + rng.normal(0, model.hba1c_test_sd)

        if test == "glucose":
            hba1c = self._hba1c(own, diabetes_onset, day, ramp)
            if hba1c == own["hba1c_healthy"]:
                return rng.normal(own["glucose_healthy"], 0.3)
            line = model.glucose_from_hba1c
            return line.intercept + line.slope * hba1c + rng.normal(0, line.sd)

        if test == "ldl":
            high = onsets.get("hyperlipidaemia", dt.date.max) <= day
            level = own["ldl_high"] if high else own["ldl_healthy"]
            level *= 1 - model.ldl_statin_reduction * ramp("atorvastatin")
            return rng.normal(level, model.ldl_test_sd)

        if test == "alt":
            uln = spec.reference(sex)[1]
            rise = config.interactions.alt_after_statin_start
            for start_day, rises in alt_rise.items():
                if (
                    rises
                    and 0 < (day - start_day).days <= STATIN_WATCH_DAYS
                    and "statin" in classes
                ):
                    return uln * rng.uniform(rise.times_uln + 0.1, rise.times_uln + 3)
            return model.alt_median * math.exp(rng.normal(0, model.alt_log_sd))

        if test == "inr":
            if "vka" not in classes:
                return rng.normal(
                    model.inr_off_warfarin.mean, model.inr_off_warfarin.sd
                )
            high = config.interactions.inr_above_4_on_warfarin
            if rng.random() < high.chance_per_test:
                return rng.uniform(high.threshold + 0.1, high.threshold + 3)
            on = model.inr_on_warfarin
            return redraw(
                lambda: rng.normal(on.mean, on.sd),
                lambda v: 1.0 <= v <= high.threshold,
                fallback=on.mean,
            )

        if test == "nt_probnp":
            hf = onsets.get("heart_failure", dt.date.max) <= day
            median = (
                model.nt_probnp_median.heart_failure
                if hf
                else model.nt_probnp_median.no_heart_failure
            )
            return median * math.exp(rng.normal(0, model.nt_probnp_log_sd))

        raise ValueError(f"no value rule for lab test {test}")

    def _hba1c(self, own, onset: dt.date | None, day: dt.date, ramp) -> float:
        """The patient's true HbA1c on `day`.

        Diabetes is diagnosed because HbA1c is high, so it rises over the year
        before the diagnosis, from the patient's healthy level to their
        diabetic level, which is at least the diagnostic threshold. After the
        diagnosis, metformin and insulin bring it down.
        """
        model = self.config.lab_model
        healthy = own["hba1c_healthy"]
        rise = dt.timedelta(days=model.hba1c_rise_before_diagnosis_days)
        if onset is None or day < onset - rise:
            return healthy
        diabetic = max(own["hba1c_diabetes"], model.hba1c_diagnosis_threshold)
        if day < onset:
            share = 1 - (onset - day) / rise
            return healthy + (diabetic - healthy) * share
        return (
            diabetic
            + model.hba1c_metformin_effect * ramp("metformin")
            + model.hba1c_insulin_effect * ramp("insulin_glargine")
        )
