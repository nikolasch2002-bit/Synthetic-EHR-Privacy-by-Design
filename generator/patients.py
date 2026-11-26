"""Patients: their demographics, and their identity kept apart from it.

`Patient` is what the clinical tables may know. `PatientIdentity` holds the
identifiers (name, address, MRN, exact birth date) and goes only to the
identity schema. Names and addresses come from Faker's Dutch locale; they are
invented, but can match a real person by chance, so they are treated as
personal data. Faker's national ID generators are never used.
"""

import datetime as dt
from dataclasses import dataclass

import numpy as np
from faker import Faker

from generator.config import Config
from generator.streams import Part, patient_rng


@dataclass(frozen=True)
class Patient:
    patient_id: int
    sex: str  # "F" or "M"
    birth_date: dt.date  # the clinical table keeps only the year


@dataclass(frozen=True)
class PatientIdentity:
    patient_id: int
    mrn: str
    given_name: str
    family_name: str
    birth_date: dt.date
    sex: str
    street_address: str
    postcode: str
    city: str
    province: str


def mrn(patient_id: int) -> str:
    """A medical record number no real person can have: the SYN- prefix."""
    return f"SYN-{patient_id:07d}"


def years_before(day: dt.date, years: int) -> dt.date:
    """The same calendar day `years` earlier (28 Feb if it would be 29 Feb)."""
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)


def draw_demographics(config: Config, patient_id: int) -> Patient:
    rng = patient_rng(config.seed, patient_id, Part.DEMOGRAPHICS)
    sex = "F" if rng.random() < config.female_share else "M"

    # Pick an age band by its share, then a birth date uniformly within it.
    shares = np.array([band.share for band in config.age_mix])
    band = int(rng.choice(len(shares), p=shares / shares.sum()))
    youngest_age = config.age_mix[band].age_from
    if band + 1 < len(config.age_mix):
        oldest_age = config.age_mix[band + 1].age_from
    else:
        oldest_age = config.max_age

    # Born on or before `latest`: at least `youngest_age` on the start date.
    # Born after `earliest`: younger than `oldest_age` on the start date.
    start = config.history.start
    latest = years_before(start, youngest_age)
    earliest = years_before(start, oldest_age) + dt.timedelta(days=1)
    offset = int(rng.integers(0, (latest - earliest).days + 1))
    return Patient(patient_id, sex, earliest + dt.timedelta(days=offset))


def draw_identity(fake: Faker, config: Config, patient: Patient) -> PatientIdentity:
    rng = patient_rng(config.seed, patient.patient_id, Part.IDENTITY)
    # Faker has its own random generator; seed it from this patient's stream.
    fake.seed_instance(int(rng.integers(2**32)))
    given = fake.first_name_female() if patient.sex == "F" else fake.first_name_male()
    return PatientIdentity(
        patient_id=patient.patient_id,
        mrn=mrn(patient.patient_id),
        given_name=given,
        family_name=fake.last_name(),
        birth_date=patient.birth_date,
        sex=patient.sex,
        street_address=fake.street_address(),
        postcode=fake.postcode(),
        city=fake.city(),
        # Drawn on its own, so it need not match the city. Fine for fake data;
        # the marts use it only as a coarse region.
        province=fake.administrative_unit(),
    )


def generate_patients(
    config: Config, population: int | None = None
) -> list[tuple[Patient, PatientIdentity]]:
    """Patients 1..population (default: the config's), with their identities."""
    fake = Faker(config.locale)
    result = []
    for patient_id in range(1, (population or config.population) + 1):
        patient = draw_demographics(config, patient_id)
        result.append((patient, draw_identity(fake, config, patient)))
    return result
