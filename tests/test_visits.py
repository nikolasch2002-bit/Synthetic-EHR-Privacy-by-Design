"""Visits: possible dates, the right department, and the configured rates."""

import datetime as dt
import math

import pytest

from generator.conditions import age_years, draw_history, years_after
from generator.config import load_config
from generator.patients import generate_patients
from generator.visits import EMERGENCY, INPATIENT, OUTPATIENT, VisitMaker

N = 2_000


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def maker(config):
    return VisitMaker(config)


@pytest.fixture(scope="module")
def cohort(config, maker):
    """(patient, history, encounters, diagnoses) for N patients."""
    rows = []
    for patient, _ in generate_patients(config, N):
        history = draw_history(config, patient)
        rows.append((patient, history, *maker.draw(patient, history)))
    return rows


def last_day(config, history):
    return min(history.death_date or config.history.end, config.history.end)


def test_no_visit_before_the_history_or_after_death(config, cohort):
    for _, history, encounters, _ in cohort:
        limit = dt.datetime.combine(last_day(config, history), dt.time(23, 59))
        for e in encounters:
            assert config.history.start <= e.start.date()
            assert e.start <= e.end <= limit


def test_outpatient_visits_are_in_clinic_hours_on_weekdays(config, cohort):
    hours = config.visits.outpatient.clinic_hours
    visits = [
        e
        for *_, encounters, _ in cohort
        for e in encounters
        if e.encounter_type == OUTPATIENT
    ]
    assert all(hours.min <= e.start.hour <= hours.max for e in visits)
    # A weekend day is kept only after 20 redraws, so almost never.
    weekdays = sum(e.start.weekday() < 5 for e in visits)
    assert weekdays / len(visits) > 0.999


def test_each_clinician_works_in_the_visits_department(maker, cohort):
    department_of = {c.clinician_id: c.department_id for c in maker.clinicians}
    for *_, encounters, _ in cohort:
        for e in encounters:
            assert department_of[e.clinician_id] == e.department_id


def test_emergency_visits_go_to_the_emergency_department(config, maker, cohort):
    emergency = maker.department_id[config.visits.emergency.department]
    for *_, encounters, _ in cohort:
        for e in encounters:
            assert (e.encounter_type == EMERGENCY) == (e.department_id == emergency)


def test_diagnoses_are_conditions_the_patient_already_has(config, cohort):
    for _, history, encounters, diagnoses in cohort:
        day_of = {e.encounter_id: e.start.date() for e in encounters}
        onset_of = {r.icd10: r.onset for r in history.conditions}
        for d in diagnoses:
            assert onset_of[d.icd10] <= day_of[d.encounter_id]


def test_a_visit_has_at_most_one_primary_diagnosis_in_its_department(
    config, maker, cohort
):
    department_of_code = {
        c.icd10: maker.department_id[c.department] for c in config.conditions.values()
    }
    for *_, encounters, diagnoses in cohort:
        primaries = {}
        for d in diagnoses:
            if d.is_primary:
                assert d.encounter_id not in primaries
                primaries[d.encounter_id] = d.icd10
        for e in encounters:
            if e.encounter_id in primaries and e.encounter_type != EMERGENCY:
                assert department_of_code[primaries[e.encounter_id]] == e.department_id


def expected_visits(config, maker, patient, history):
    """Expected counts per type, recomputed here from the config's numbers."""
    visits = config.visits
    onsets = {r.condition: r.onset for r in history.conditions}
    expected = {OUTPATIENT: 0.0, EMERGENCY: 0.0, INPATIENT: 0.0}
    year_start, end = config.history.start, last_day(config, history)
    while year_start <= end:
        year_end = min(years_after(year_start, 1) - dt.timedelta(days=1), end)
        exposure = ((year_end - year_start).days + 1) / 365.25
        present = [c for c, onset in onsets.items() if onset <= year_start]
        hf = "heart_failure" in present
        expected[OUTPATIENT] += exposure * (
            visits.outpatient.base_per_year
            + visits.outpatient.per_condition_per_year * len(present)
        )
        expected[EMERGENCY] += (
            exposure
            * visits.emergency.per_year
            * (visits.emergency.heart_failure_factor if hf else 1)
        )
        expected[INPATIENT] += (
            exposure
            * maker.inpatient_rate(age_years(patient.birth_date, year_start))
            * (visits.inpatient.heart_failure_factor if hf else 1)
        )
        year_start = years_after(year_start, 1)
    return expected


@pytest.mark.parametrize("encounter_type", [OUTPATIENT, EMERGENCY, INPATIENT])
def test_visit_counts_match_the_configured_rates(config, maker, cohort, encounter_type):
    expected = observed = 0.0
    for patient, history, encounters, _ in cohort:
        expected += expected_visits(config, maker, patient, history)[encounter_type]
        observed += sum(e.encounter_type == encounter_type for e in encounters)
    # Counts are Poisson, so the variance equals the mean.
    assert abs(observed - expected) < 4 * math.sqrt(expected)


def test_inpatient_rate_follows_the_configured_age_bands(config, maker):
    rates = config.visits.inpatient.per_year
    assert maker.inpatient_rate(18.0) == rates.rate[0]
    assert maker.inpatient_rate(80.0) == rates.rate[-1]  # CBS 2024: 13.5% at 75+


@pytest.mark.parametrize("index", [0, 1, 999, N - 1])
def test_visits_do_not_depend_on_other_patients(config, cohort, index):
    patient, history, encounters, diagnoses = cohort[index]
    assert VisitMaker(config).draw(patient, history) == (encounters, diagnoses)


def test_clinicians_are_the_same_in_every_run(config, maker):
    assert VisitMaker(config).clinicians == maker.clinicians
    assert (
        len(maker.clinicians)
        == len(config.departments) * config.clinicians_per_department
    )
