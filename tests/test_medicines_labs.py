"""Medicines and labs: clinically consistent, and the planted interactions at their rates."""

import datetime as dt
import itertools
import math
from dataclasses import dataclass

import pytest

from generator.conditions import age_years, draw_history
from generator.config import load_config
from generator.kidney import KidneyCourse, ckd_epi_2021, creatinine_for_egfr
from generator.labs import LabMaker, hyperkalaemia_log_odds
from generator.medications import (
    MedicationOrder,
    draw_therapies,
    new_starts,
    orders_for,
)
from generator.patients import generate_patients
from generator.visits import VisitMaker

N = 3_000


@dataclass
class Record:
    patient: object
    history: object
    kidney: object
    plan: object
    orders: list
    labs: list
    raas: list  # planted hyperkalaemia decisions


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def cohort(config):
    visits, labs = VisitMaker(config), LabMaker(config)
    records = []
    for patient, _ in generate_patients(config, N):
        history = draw_history(config, patient)
        kidney = KidneyCourse(config, patient, history)
        plan = draw_therapies(config, patient, history)
        encounters, diagnoses = visits.draw(patient, history)
        results, raas = labs.draw(patient, history, kidney, plan, encounters, diagnoses)
        records.append(
            Record(
                patient,
                history,
                kidney,
                plan,
                orders_for(config, patient, plan),
                results,
                raas,
            )
        )
    return records


def onsets(record) -> dict:
    return {r.condition: r.onset for r in record.history.conditions}


def last_day(config, record):
    return min(record.history.death_date or config.history.end, config.history.end)


def within(observed: float, expected: float, variance: float) -> bool:
    """Within 4 standard errors."""
    return abs(observed - expected) <= 4 * math.sqrt(max(variance, 1e-9))


# --- The equations ---


@pytest.mark.parametrize("sex", ["F", "M"])
@pytest.mark.parametrize("egfr", [8.0, 25.0, 59.0, 95.0, 120.0])
def test_creatinine_for_egfr_inverts_ckd_epi(sex, egfr):
    creatinine = creatinine_for_egfr(egfr, 63.0, sex)
    assert ckd_epi_2021(creatinine, 63.0, sex) == pytest.approx(egfr)


def test_ckd_epi_2021_matches_a_worked_value():
    # A 60-year-old woman with creatinine 1.0 mg/dL (88.4 µmol/L): about 65 by CKD-EPI 2021.
    assert ckd_epi_2021(88.4, 60, "F") == pytest.approx(64.6, abs=0.5)


def test_hyperkalaemia_log_odds_follow_the_config(config):
    c = config.interactions.hyperkalaemia_after_raas_start.log_odds
    base = {
        "egfr": 70.0,
        "potassium": 4.5,
        "diabetes": False,
        "age": 60.0,
        "combination": False,
        "diuretic": False,
    }
    assert hyperkalaemia_log_odds(config, **base) == pytest.approx(c.intercept)
    assert hyperkalaemia_log_odds(
        config, **{**base, "combination": True}
    ) - c.intercept == pytest.approx(c.combination)
    assert hyperkalaemia_log_odds(
        config, **{**base, "egfr": 40.0}
    ) - c.intercept == pytest.approx(2 * c.egfr_per_10_below_60)
    assert hyperkalaemia_log_odds(
        config, **{**base, "diuretic": True}
    ) - c.intercept == pytest.approx(c.loop_or_thiazide)


def order(config, drug, day: dt.date) -> MedicationOrder:
    d = config.drugs[drug]
    return MedicationOrder(1, 1, drug, d.atc, d.dose, d.unit, d.frequency, day, day)


def test_a_new_start_needs_180_days_without_an_order_of_its_class(config):
    first = config.history.start + dt.timedelta(days=200)
    orders = [
        order(config, "ramipril", first),
        order(
            config, "ramipril", first + dt.timedelta(days=180)
        ),  # 180 days later: a repeat
        order(
            config, "ramipril", first + dt.timedelta(days=361)
        ),  # 181 days after that: a start
        order(
            config, "losartan", first + dt.timedelta(days=10)
        ),  # another class: its own start
    ]
    starts = [(s.drug_class, (s.day - first).days) for s in new_starts(config, orders)]
    assert starts == [("ace_inhibitor", 0), ("arb", 10), ("ace_inhibitor", 361)]


# --- Clinically consistent ---


def indications(config) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for condition, choices in config.treatment.items():
        for choice in choices:
            for drug in choice.drugs:
                result.setdefault(drug, set()).add(condition)
    result.setdefault("spironolactone", set()).add("heart_failure")
    return result


def test_no_medicine_before_its_indication(config, cohort):
    reasons = indications(config)
    for r in cohort:
        when = onsets(r)
        for t in r.plan.therapies:
            assert any(when.get(c, dt.date.max) <= t.start for c in reasons[t.drug]), t


def test_orders_fall_inside_the_patients_life_and_do_not_overlap(config, cohort):
    for r in cohort:
        by_drug = {}
        for o in r.orders:
            assert config.history.start <= o.start <= o.stop <= last_day(config, r)
            by_drug.setdefault(o.drug, []).append(o)
        for drug_orders in by_drug.values():
            drug_orders.sort(key=lambda o: o.start)
            for a, b in itertools.pairwise(drug_orders):
                assert a.stop < b.start


def test_lab_values_are_within_physiological_limits_and_rounded(config, cohort):
    for r in cohort:
        for lab in r.labs:
            spec = config.lab_tests[lab.test]
            assert spec.limit_low <= lab.value <= spec.limit_high
            assert lab.value == round(lab.value, spec.decimals)
            assert lab.ordered_at <= lab.resulted_at


def test_reference_ranges_differ_by_sex_where_configured(config, cohort):
    for r in cohort:
        for lab in r.labs:
            if lab.test == "creatinine":
                assert lab.ref_high == (90 if r.patient.sex == "F" else 110)


def test_egfr_is_computed_from_the_creatinine_drawn_with_it(cohort):
    for r in cohort[:500]:
        creatinine = {
            lab.ordered_at: lab.value for lab in r.labs if lab.test == "creatinine"
        }
        for lab in r.labs:
            if lab.test == "egfr":
                age = age_years(r.patient.birth_date, lab.ordered_at.date())
                # Creatinine is reported to the whole µmol/L, eGFR to the whole unit.
                assert (
                    abs(
                        ckd_epi_2021(creatinine[lab.ordered_at], age, r.patient.sex)
                        - lab.value
                    )
                    < 2
                )


def test_egfr_agrees_with_ckd_on_the_problem_list(cohort):
    with_ckd = without = low_with = low_without = 0
    for r in cohort:
        ckd = onsets(r).get("ckd")
        for lab in r.labs:
            if lab.test != "egfr":
                continue
            if ckd is not None and lab.ordered_at.date() >= ckd:
                with_ckd += 1
                low_with += lab.value < 60
            elif ckd is None:
                without += 1
                low_without += lab.value < 60
    assert low_with / with_ckd > 0.95
    # Older patients near 60, plus test noise: some reduced eGFR goes undiagnosed, as in
    # real care. Kept rare.
    assert low_without / without < 0.10


def test_hba1c_is_higher_in_diabetes(cohort):
    diabetic, other = [], []
    for r in cohort:
        dm = onsets(r).get("type2_diabetes", dt.date.max)
        for lab in r.labs:
            if lab.test == "hba1c":
                (diabetic if lab.ordered_at.date() >= dm else other).append(lab.value)
    assert sum(diabetic) / len(diabetic) - sum(other) / len(other) > 10


def test_diabetes_is_diagnosed_with_a_high_hba1c(config, cohort):
    # The diagnosing test, on the day of diagnosis, outside a visit.
    threshold = config.lab_model.hba1c_diagnosis_threshold
    at_diagnosis = [
        lab.value
        for r in cohort
        if (onset := onsets(r).get("type2_diabetes")) and onset >= config.history.start
        for lab in r.labs
        if lab.test == "hba1c"
        and lab.encounter_id is None
        and lab.ordered_at.date() == onset
    ]
    assert len(at_diagnosis) > 50
    # The true level is at least the threshold; the test adds a little noise.
    assert sum(v >= threshold - 4 for v in at_diagnosis) / len(at_diagnosis) > 0.97


def mean_change_after_start(
    cohort, drug, test, before_days=365, after=(120, 365)
) -> float:
    changes = []
    for r in cohort:
        start = next((t.start for t in r.plan.therapies if t.drug == drug), None)
        if start is None:
            continue
        values = [
            (lab.ordered_at.date(), lab.value) for lab in r.labs if lab.test == test
        ]
        pre = [v for d, v in values if 0 < (start - d).days <= before_days]
        post = [v for d, v in values if after[0] <= (d - start).days <= after[1]]
        if pre and post:
            changes.append(sum(post) / len(post) - sum(pre) / len(pre))
    assert len(changes) > 20
    return sum(changes) / len(changes)


def test_hba1c_falls_after_metformin_starts(config, cohort):
    expected = config.lab_model.hba1c_metformin_effect  # -10 mmol/mol at full effect
    assert mean_change_after_start(cohort, "metformin", "hba1c") < expected / 2


def test_ldl_falls_after_a_statin_starts(cohort):
    assert mean_change_after_start(cohort, "atorvastatin", "ldl") < -0.8


# --- The planted interactions ---


def potassium_in_window(record, start_day, window):
    return [
        lab.value
        for lab in record.labs
        if lab.test == "potassium"
        and 1 <= (lab.ordered_at.date() - start_day).days <= window
    ]


def test_hyperkalaemia_is_found_exactly_where_it_was_planted(config, cohort):
    hk = config.interactions.hyperkalaemia_after_raas_start
    measured = 0
    for r in cohort:
        for d in r.raas:
            values = potassium_in_window(r, d.start.day, hk.window_days)
            if values:
                measured += 1
                assert (max(values) >= hk.threshold) == d.event
    assert measured > 100


def test_hyperkalaemia_events_match_the_formula(cohort):
    decisions = [d for r in cohort for d in r.raas]
    observed = sum(d.event for d in decisions)
    expected = sum(d.chance for d in decisions)
    assert within(observed, expected, sum(d.chance * (1 - d.chance) for d in decisions))


def test_potassium_is_followed_up_after_a_raas_start_at_the_configured_rate(
    config, cohort
):
    follow = config.lab_rules.potassium_after_raas_start
    starts = followed = 0
    for r in cohort:
        for d in r.raas:
            if d.start.day + dt.timedelta(days=follow.days.max) > last_day(config, r):
                continue  # the follow-up day may fall after death or the end
            starts += 1
            followed += any(
                lab.test == "potassium"
                and lab.encounter_id is None
                and follow.days.min
                <= (lab.ordered_at.date() - d.start.day).days
                <= follow.days.max
                for lab in r.labs
            )
    p = follow.chance
    assert within(followed, starts * p, starts * p * (1 - p))


def outside_hyperkalaemia_windows(config, record, lab) -> bool:
    window = config.interactions.hyperkalaemia_after_raas_start.window_days
    return not any(
        1 <= (lab.ordered_at.date() - d.start.day).days <= window for d in record.raas
    )


def test_hypokalaemia_on_a_diuretic_at_the_configured_rate(config, cohort):
    low = config.interactions.hypokalaemia_on_diuretic
    tests = hits = 0
    for r in cohort:
        for lab in r.labs:
            on = r.plan.classes_on(lab.ordered_at.date())
            diuretic = on & {"loop_diuretic", "thiazide"}
            if (
                lab.test == "potassium"
                and diuretic
                and outside_hyperkalaemia_windows(config, r, lab)
            ):
                tests += 1
                hits += lab.value < low.threshold
    p = low.chance_per_test
    assert tests > 500
    assert within(hits, tests * p, tests * p * (1 - p))


def test_inr_above_4_on_warfarin_at_the_configured_rate(config, cohort):
    high = config.interactions.inr_above_4_on_warfarin
    tests = hits = 0
    for r in cohort:
        for lab in r.labs:
            if lab.test == "inr" and "vka" in r.plan.classes_on(lab.ordered_at.date()):
                tests += 1
                hits += lab.value > high.threshold
    p = high.chance_per_test
    assert tests > 500
    assert within(hits, tests * p, tests * p * (1 - p))


def test_inr_is_checked_every_four_weeks_on_warfarin(config, cohort):
    for r in cohort:
        days = sorted(
            lab.ordered_at.date()
            for lab in r.labs
            if lab.test == "inr" and lab.encounter_id is None
        )
        gaps = {(b - a).days for a, b in itertools.pairwise(days)}
        # 28 days apart, except where a stop and a restart meet.
        assert not gaps or min(gaps) >= config.lab_rules.inr_monitoring_days - 1


def test_metformin_is_continued_below_egfr_30_at_the_configured_rate(config, cohort):
    # Decided at the first eGFR result below 30 during a metformin therapy:
    # stopped within 30 days, or continued.
    keep = 1 - config.medication_rules.metformin_stop_below_egfr_30
    users = continued = 0
    for r in cohort:
        for t in r.plan.therapies:
            if t.drug != "metformin":
                continue
            low = sorted(
                lab.ordered_at.date()
                for lab in r.labs
                if lab.test == "egfr"
                and lab.value < 30
                and t.start <= lab.ordered_at.date() <= t.stop
            )
            if not low or low[0] + dt.timedelta(days=31) > last_day(config, r):
                continue
            users += 1
            continued += t.stop > low[0] + dt.timedelta(days=30)
    assert users > 10
    assert within(continued, users * keep, users * keep * (1 - keep))


def test_alt_rises_after_a_statin_only_rarely(config, cohort):
    rise = config.interactions.alt_after_statin_start
    starts = risen = 0
    for r in cohort:
        statin = [s for s in new_starts(config, r.orders, classes=("statin",))]
        for s in statin:
            values = [
                (lab.value, lab.ref_high)
                for lab in r.labs
                if lab.test == "alt" and 1 <= (lab.ordered_at.date() - s.day).days <= 84
            ]
            if values:
                starts += 1
                risen += any(v > rise.times_uln * uln for v, uln in values)
    p = rise.chance
    assert starts > 50
    assert within(risen, starts * p, starts * p * (1 - p))


# --- Reproducible ---


@pytest.mark.parametrize("index", [0, 7, N - 1])
def test_medicines_and_labs_do_not_depend_on_other_patients(config, cohort, index):
    r = cohort[index]
    encounters, diagnoses = VisitMaker(config).draw(r.patient, r.history)
    kidney = KidneyCourse(config, r.patient, r.history)
    plan = draw_therapies(config, r.patient, r.history)
    results, raas = LabMaker(config).draw(
        r.patient, r.history, kidney, plan, encounters, diagnoses
    )
    assert plan.therapies == r.plan.therapies
    assert results == r.labs
    assert raas == r.raas
