"""Departments, clinicians, visits and the diagnoses recorded at each visit.

The rules are in docs/clinical-rules.md, sections 6 and 7. Year by year until
death or the end of the history, a patient has outpatient visits (more with
more conditions), emergency visits and admissions (more when older, and more
with heart failure). A visit is for one of the conditions the patient has on
that day, and goes to the department that treats it.
"""

import datetime as dt
from dataclasses import dataclass

from faker import Faker

from generator.conditions import (
    ClinicalHistory,
    age_years,
    random_day,
    years_after,
)
from generator.config import Config
from generator.patients import Patient
from generator.streams import Part, patient_rng

OUTPATIENT, EMERGENCY, INPATIENT = "outpatient", "emergency", "inpatient"
# Encounter IDs are patient_id * this + a counter, so a patient's IDs do not
# depend on other patients.
ENCOUNTERS_PER_PATIENT_MAX = 10_000


@dataclass(frozen=True)
class Department:
    department_id: int
    code: str
    name: str


@dataclass(frozen=True)
class Clinician:
    clinician_id: int
    department_id: int
    given_name: str
    family_name: str


@dataclass(frozen=True)
class Encounter:
    encounter_id: int
    patient_id: int
    department_id: int
    clinician_id: int
    encounter_type: str
    start: dt.datetime
    end: dt.datetime


@dataclass(frozen=True)
class EncounterDiagnosis:
    encounter_id: int
    icd10: str
    is_primary: bool


def make_departments(config: Config) -> list[Department]:
    return [
        Department(i, code, code.replace("_", " ").capitalize())
        for i, code in enumerate(config.departments, start=1)
    ]


def make_clinicians(config: Config, departments: list[Department]) -> list[Clinician]:
    """The same clinicians whatever the population size: one shared stream."""
    rng = patient_rng(config.seed, 0, Part.CLINICIANS)
    fake = Faker(config.locale)
    fake.seed_instance(int(rng.integers(2**32)))
    clinicians = []
    for department in departments:
        for _ in range(config.clinicians_per_department):
            given = (
                fake.first_name_female()
                if rng.random() < 0.5
                else fake.first_name_male()
            )
            clinicians.append(
                Clinician(
                    len(clinicians) + 1,
                    department.department_id,
                    given,
                    fake.last_name(),
                )
            )
    return clinicians


class VisitMaker:
    """Draws one patient's visits; holds the lookups every patient shares."""

    def __init__(self, config: Config):
        self.config = config
        self.departments = make_departments(config)
        self.clinicians = make_clinicians(config, self.departments)
        self.department_id = {d.code: d.department_id for d in self.departments}
        self.clinician_ids = {
            d.department_id: [
                c.clinician_id
                for c in self.clinicians
                if c.department_id == d.department_id
            ]
            for d in self.departments
        }

    def inpatient_rate(self, age: float) -> float:
        rates = self.config.visits.inpatient.per_year
        band = max(i for i, a in enumerate(rates.age_from) if a <= age)
        return rates.rate[band]

    def draw(
        self, patient: Patient, history: ClinicalHistory
    ) -> tuple[list[Encounter], list[EncounterDiagnosis]]:
        config, visits = self.config, self.config.visits
        rng = patient_rng(config.seed, patient.patient_id, Part.VISITS)
        onsets = {r.condition: r.onset for r in history.conditions}
        last_day = min(history.death_date or config.history.end, config.history.end)
        # A visit cannot end after the patient has died or the history ends.
        limit = dt.datetime.combine(last_day, dt.time(23, 59))

        encounters: list[Encounter] = []
        diagnoses: list[EncounterDiagnosis] = []
        year_start = config.history.start
        while year_start <= last_day:
            year_end = min(years_after(year_start, 1) - dt.timedelta(days=1), last_day)
            # The rates are per year; a part-year (the year of death) gets its share.
            exposure = ((year_end - year_start).days + 1) / 365.25
            present = [
                c for c in config.conditions if onsets.get(c, dt.date.max) <= year_start
            ]
            hf_ed = (
                visits.emergency.heart_failure_factor
                if "heart_failure" in present
                else 1.0
            )
            hf_in = (
                visits.inpatient.heart_failure_factor
                if "heart_failure" in present
                else 1.0
            )
            age = age_years(patient.birth_date, year_start)

            out_rate = (
                visits.outpatient.base_per_year
                + visits.outpatient.per_condition_per_year * len(present)
            )
            counts = [
                (OUTPATIENT, rng.poisson(out_rate * exposure)),
                (EMERGENCY, rng.poisson(visits.emergency.per_year * hf_ed * exposure)),
                (INPATIENT, rng.poisson(self.inpatient_rate(age) * hf_in * exposure)),
            ]
            for encounter_type, count in counts:
                for _ in range(int(count)):
                    day = random_day(rng, year_start, year_end)
                    if encounter_type == OUTPATIENT:
                        # Clinics are closed at weekends: draw again (a few tries).
                        for _ in range(20):
                            if day.weekday() < 5:
                                break
                            day = random_day(rng, year_start, year_end)
                    on_day = [
                        c
                        for c in config.conditions
                        if onsets.get(c, dt.date.max) <= day
                    ]
                    encounter_id = (
                        patient.patient_id * ENCOUNTERS_PER_PATIENT_MAX
                        + len(encounters)
                        + 1
                    )
                    encounter, dx = self._visit(
                        rng,
                        encounter_id,
                        patient,
                        encounter_type,
                        day,
                        on_day,
                        limit,
                        age,
                    )
                    encounters.append(encounter)
                    diagnoses.extend(dx)
            year_start = years_after(year_start, 1)

        if len(encounters) >= ENCOUNTERS_PER_PATIENT_MAX:
            raise RuntimeError(f"patient {patient.patient_id} has too many encounters")
        return encounters, diagnoses

    def _visit(
        self, rng, encounter_id, patient, encounter_type, day, on_day, limit, age
    ):
        config, visits = self.config, self.config.visits
        # The condition this visit is for, if the patient has any yet.
        reason = str(rng.choice(on_day)) if on_day else None

        if encounter_type == EMERGENCY:
            department = visits.emergency.department
        elif reason:
            department = config.conditions[reason].department
        else:
            department = visits.outpatient.default_department
        department_id = self.department_id[department]
        clinician_id = int(rng.choice(self.clinician_ids[department_id]))

        if encounter_type == OUTPATIENT:
            hours = visits.outpatient.clinic_hours
            start = dt.datetime.combine(
                day,
                dt.time(
                    int(rng.integers(hours.min, hours.max + 1)),
                    5 * int(rng.integers(0, 12)),
                ),
            )
            minutes = visits.outpatient.duration_minutes
            end = start + dt.timedelta(
                minutes=int(rng.integers(minutes.min, minutes.max + 1))
            )
        elif encounter_type == EMERGENCY:
            start = dt.datetime.combine(day, dt.time()) + dt.timedelta(
                minutes=int(rng.integers(0, 24 * 60))
            )
            hours = visits.emergency.duration_hours
            end = start + dt.timedelta(
                minutes=int(rng.integers(hours.min * 60, hours.max * 60 + 1))
            )
        else:
            start = dt.datetime.combine(day, dt.time()) + dt.timedelta(
                minutes=int(rng.integers(0, 24 * 60))
            )
            stay = visits.inpatient.length_of_stay_days
            days = int(rng.integers(stay.min, stay.max + 1))
            if age >= 75 or (reason == "heart_failure"):
                # Longer stays for older and heart-failure patients: the longer of two draws.
                days = max(days, int(rng.integers(stay.min, stay.max + 1)))
            end = start + dt.timedelta(days=days)
        end = max(start, min(end, limit))

        encounter = Encounter(
            encounter_id,
            patient.patient_id,
            department_id,
            clinician_id,
            encounter_type,
            start,
            end,
        )
        diagnoses = []
        if reason:
            diagnoses.append(
                EncounterDiagnosis(encounter_id, config.conditions[reason].icd10, True)
            )
            if encounter_type == INPATIENT:
                # An admission records every other known condition as secondary.
                others = [c for c in on_day if c != reason]
            else:
                # A clinic visit records the other conditions that department treats.
                others = [
                    c
                    for c in on_day
                    if c != reason and config.conditions[c].department == department
                ]
            diagnoses.extend(
                EncounterDiagnosis(encounter_id, config.conditions[c].icd10, False)
                for c in others
            )
        return encounter, diagnoses
