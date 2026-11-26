"""Conditions and death: the rules in docs/clinical-rules.md, and plausible dates."""

import datetime as dt
import math

import pytest

from generator.conditions import (
    age_years,
    baseline_chance,
    draw_history,
    prevalence,
    yearly_death_chance,
    years_after,
)
from generator.config import MIN_AGE, load_config
from generator.patients import generate_patients

N = 5_000


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def cohort(config):
    """(patient, history) pairs."""
    return [(p, draw_history(config, p)) for p, _ in generate_patients(config, N)]


def baseline_conditions(config, history) -> set[str]:
    return {r.condition for r in history.conditions if r.onset < config.history.start}


def odds(p: float) -> float:
    return p / (1 - p)


# --- The rules themselves, checked against the config's numbers ---


def test_prevalence_equals_the_config_at_each_band_midpoint(config):
    rates = config.conditions["hypertension"].prevalence_per_1000
    # 70-74 is the band whose midpoint is 72.5; the CBS rate there is 450 per 1,000.
    band = rates.age_from.index(70)
    assert prevalence(config, "hypertension", "M", 72.5) == pytest.approx(
        rates.male[band] / 1000
    )
    assert prevalence(config, "hypertension", "F", 72.5) == pytest.approx(
        rates.female[band] / 1000
    )


def test_type2_diabetes_is_scaled_to_its_share_of_all_diabetes(config):
    rates = config.conditions["type2_diabetes"].prevalence_per_1000
    band = rates.age_from.index(70)
    assert prevalence(config, "type2_diabetes", "M", 72.5) == pytest.approx(
        rates.male[band] / 1000 * 0.91
    )


def test_an_odds_ratio_multiplies_the_odds(config):
    alone = baseline_chance(config, "heart_failure", "M", 70.0, set())
    with_af = baseline_chance(
        config, "heart_failure", "M", 70.0, {"atrial_fibrillation"}
    )
    assert odds(with_af) / odds(alone) == pytest.approx(4.0)  # config: AF raises HF x4
    both = baseline_chance(
        config, "heart_failure", "M", 70.0, {"atrial_fibrillation", "hypertension"}
    )
    assert odds(both) / odds(alone) == pytest.approx(4.0 * 2.0)


def test_a_hazard_ratio_raises_survival_to_its_power(config):
    p = yearly_death_chance(config, "M", 80.0, set())
    assert p == pytest.approx(0.05157)  # CBS 2019, men aged 80
    with_hf = yearly_death_chance(config, "M", 80.0, {"heart_failure"})
    assert 1 - with_hf == pytest.approx((1 - p) ** 2.5)  # config: HF hazard ratio 2.5


# --- The generated cohort follows the rules ---


@pytest.mark.parametrize("name", list(load_config().conditions))
def test_baseline_prevalence_matches_the_expected_chance(config, cohort, name):
    # Expected count: each patient's chance, given the conditions drawn before
    # this one. The observed count must be within 4 standard errors of it.
    names = list(config.conditions)
    earlier = set(names[: names.index(name)])
    expected = variance = observed = 0.0
    for patient, history in cohort:
        present = baseline_conditions(config, history)
        age = age_years(patient.birth_date, config.history.start)
        p = baseline_chance(config, name, patient.sex, age, present & earlier)
        expected += p
        variance += p * (1 - p)
        observed += name in present
    assert abs(observed - expected) < 4 * math.sqrt(variance)


def test_first_year_deaths_match_the_expected_chance(config, cohort):
    start = config.history.start
    year_end = years_after(start, 1)
    expected = variance = observed = 0.0
    for patient, history in cohort:
        age = age_years(patient.birth_date, start)
        p = yearly_death_chance(
            config, patient.sex, age, baseline_conditions(config, history)
        )
        expected += p
        variance += p * (1 - p)
        observed += history.death_date is not None and history.death_date < year_end
    assert abs(observed - expected) < 4 * math.sqrt(variance)


def test_new_diagnoses_happen_throughout_follow_up(config, cohort):
    start = config.history.start
    years = {r.onset.year for _, h in cohort for r in h.conditions if r.onset >= start}
    assert years == set(range(start.year, config.history.end.year + 1))


# --- Dates are clinically possible ---


def test_no_onset_before_18_or_after_the_history_ends(config, cohort):
    for patient, history in cohort:
        adult = years_after(patient.birth_date, MIN_AGE)
        for record in history.conditions:
            assert adult <= record.onset <= config.history.end


def test_prevalent_onsets_fall_in_the_configured_window(config, cohort):
    # 1 to 15 years before the start, but not before 18; someone who turned 18
    # less than a year before the start has an onset between then and the start.
    start = config.history.start
    window = config.prevalent_onset_years_before
    for patient, history in cohort:
        adult = years_after(patient.birth_date, MIN_AGE)
        earliest = max(years_after(start, -window.max), adult)
        latest = years_after(start, -window.min)
        if earliest > latest:
            latest = start - dt.timedelta(days=1)
        for record in history.conditions:
            if record.onset < start:
                assert earliest <= record.onset <= latest


def test_no_diagnosis_after_death_and_death_inside_the_history(config, cohort):
    for _, history in cohort:
        if history.death_date is None:
            continue
        assert config.history.start <= history.death_date <= config.history.end
        assert all(r.onset <= history.death_date for r in history.conditions)


def test_each_condition_appears_at_most_once_per_patient(cohort):
    for _, history in cohort:
        names = [r.condition for r in history.conditions]
        assert len(names) == len(set(names))


# --- Reproducible, and independent of other patients ---


@pytest.mark.parametrize("index", [0, 1, 776, N - 1])
def test_a_history_does_not_depend_on_other_patients(config, cohort, index):
    patient, history = cohort[index]
    assert draw_history(config, patient) == history


def test_different_seed_gives_different_histories(config, cohort):
    other = config.model_copy(update={"seed": config.seed + 1})
    patients = [p for p, _ in cohort[:200]]
    assert [draw_history(other, p) for p in patients] != [h for _, h in cohort[:200]]
