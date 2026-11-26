"""Conditions on the problem list, their onset dates, and the date of death.

The rules are in docs/clinical-rules.md, sections 2 to 5:
- On the start date, conditions are drawn in the config's order. Each one's
  chance starts from its prevalence for the patient's age and sex, raised by
  the odds ratios of conditions already drawn. Its onset is 1 to 15 years
  earlier, but never before the patient turned 18.
- Then, year by year until death or the end of the history: new diagnoses,
  at the yearly rate implied by how prevalence rises with age; and death, at
  the life table's rate, raised by the conditions present at the year's start.
"""

import bisect
import datetime as dt
import math
from dataclasses import dataclass

import numpy as np

from generator.config import MIN_AGE, Config
from generator.patients import Patient, years_before
from generator.streams import Part, patient_rng


@dataclass(frozen=True)
class ConditionRecord:
    patient_id: int
    condition: str
    icd10: str
    onset: dt.date


@dataclass(frozen=True)
class ClinicalHistory:
    patient_id: int
    conditions: tuple[ConditionRecord, ...]  # sorted by onset
    death_date: dt.date | None


def years_after(day: dt.date, years: int) -> dt.date:
    return years_before(day, -years)


def age_years(birth: dt.date, day: dt.date) -> float:
    return (day - birth).days / 365.25


def logit(p: float) -> float:
    return math.log(p / (1 - p))


def expit(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def prevalence(config: Config, name: str, sex: str, age: float) -> float:
    """The configured prevalence, as a chance between 0 and 1.

    The config gives one value per age band. Taking it as a step would put
    every new diagnosis on a band's first birthday, so values are joined by
    straight lines between band midpoints, and held flat beyond the first and
    last midpoints. The last band runs to the config's max_age.
    """
    condition = config.conditions[name]
    rates = condition.prevalence_per_1000
    band_ends = [*rates.age_from[1:], config.max_age]
    midpoints = [(a + b) / 2 for a, b in zip(rates.age_from, band_ends, strict=True)]
    per_1000 = rates.female if sex == "F" else rates.male
    return (
        float(np.interp(age, midpoints, per_1000)) / 1000 * condition.prevalence_scale
    )


def baseline_chance(
    config: Config, name: str, sex: str, age: float, present: set[str]
) -> float:
    """Chance of having the condition on the start date, given those drawn before it."""
    p = prevalence(config, name, sex, age)
    if p <= 0 or p >= 1:
        return min(max(p, 0.0), 1.0)
    # An odds ratio multiplies the odds, so it adds its log to the log-odds.
    raised = sum(
        math.log(odds_ratio)
        for other, odds_ratio in config.conditions[name].raised_by.items()
        if other in present
    )
    return expit(logit(p) + raised)


def yearly_incidence(config: Config, name: str, sex: str, age: float) -> float:
    """Chance of a new diagnosis within a year, for someone without it.

    The rise in prevalence from this age to the next, divided by the share
    still free of the condition. Where prevalence falls with age, it is 0.
    """
    now = prevalence(config, name, sex, age)
    later = prevalence(config, name, sex, age + 1)
    if now >= 1:
        return 0.0
    return max(0.0, (later - now) / (1 - now))


def yearly_death_chance(
    config: Config, sex: str, age: float, present: set[str]
) -> float:
    """Chance of dying within a year, raised by the conditions present."""
    mortality = config.mortality
    # The life table's value holds from its age up to the next listed age.
    band = max(bisect.bisect_right(mortality.age_from, age) - 1, 0)
    p = (mortality.female if sex == "F" else mortality.male)[band]
    hazard_ratio = math.prod(mortality.hazard_ratios.get(c, 1.0) for c in present)
    # A hazard ratio raises survival to its power: (1 - p) ** HR.
    return 1 - (1 - p) ** hazard_ratio


def random_day(rng: np.random.Generator, first: dt.date, last: dt.date) -> dt.date:
    """A day between `first` and `last`, both included, each equally likely."""
    return first + dt.timedelta(days=int(rng.integers(0, (last - first).days + 1)))


def prevalent_onset(
    rng: np.random.Generator, config: Config, patient: Patient
) -> dt.date:
    """Onset of a condition present on the start date: 1 to 15 years earlier, after 18."""
    start = config.history.start
    window = config.prevalent_onset_years_before
    adult = years_after(patient.birth_date, MIN_AGE)
    first = max(years_before(start, window.max), adult)
    last = years_before(start, window.min)
    if first > last:  # turned 18 less than a year before the start
        last = start - dt.timedelta(days=1)
        first = min(first, last)
    return random_day(rng, first, last)


def draw_history(config: Config, patient: Patient) -> ClinicalHistory:
    conditions_rng = patient_rng(config.seed, patient.patient_id, Part.CONDITIONS)
    death_rng = patient_rng(config.seed, patient.patient_id, Part.DEATH)
    start, end = config.history.start, config.history.end
    sex, birth = patient.sex, patient.birth_date

    onsets: dict[str, dt.date] = {}
    age = age_years(birth, start)
    for name in config.conditions:  # in draw order
        if conditions_rng.random() < baseline_chance(
            config, name, sex, age, set(onsets)
        ):
            onsets[name] = prevalent_onset(conditions_rng, config, patient)

    death_date = None
    year_start = start
    while year_start <= end and death_date is None:
        year_end = min(years_after(year_start, 1) - dt.timedelta(days=1), end)
        age = age_years(birth, year_start)
        present = set(onsets)  # conditions at the start of this year

        new = {}
        for name in config.conditions:
            if name in onsets:
                continue
            if conditions_rng.random() < yearly_incidence(config, name, sex, age):
                new[name] = random_day(conditions_rng, year_start, year_end)

        if death_rng.random() < yearly_death_chance(config, sex, age, present):
            death_date = random_day(death_rng, year_start, year_end)
            # Nobody is diagnosed after they have died.
            new = {name: day for name, day in new.items() if day <= death_date}

        onsets.update(new)
        year_start = years_after(year_start, 1)

    records = tuple(
        sorted(
            (
                ConditionRecord(
                    patient.patient_id, name, config.conditions[name].icd10, day
                )
                for name, day in onsets.items()
            ),
            key=lambda r: (r.onset, r.condition),
        )
    )
    return ClinicalHistory(patient.patient_id, records, death_date)
