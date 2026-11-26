"""Patients: no real identifiers, the configured age and sex mix, reproducible."""

import dataclasses
import re

import pytest
from faker import Faker

from generator.config import MIN_AGE, load_config
from generator.patients import (
    Patient,
    draw_demographics,
    draw_identity,
    generate_patients,
)

N = 5_000  # large enough for the share checks below, still fast


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def patients(config):
    return generate_patients(config, N)


def age_on(birth, day) -> int:
    """Age in whole years on `day`."""
    return day.year - birth.year - ((day.month, day.day) < (birth.month, birth.day))


def test_every_mrn_has_the_syn_prefix_and_is_unique(patients):
    mrns = [identity.mrn for _, identity in patients]
    assert all(re.fullmatch(r"SYN-\d{7}", m) for m in mrns)
    assert len(set(mrns)) == len(mrns)


def test_no_number_shaped_like_a_national_id(patients):
    # A Dutch citizen service number (BSN) has 9 digits. No identity field
    # may contain a run of 9 or more digits, whatever the separators.
    for _, identity in patients:
        for value in dataclasses.asdict(identity).values():
            digits_only = re.sub(r"[\s.\-]", "", str(value))
            assert not re.search(r"\d{9,}", digits_only), value


def test_clinical_patient_holds_no_identifiers():
    fields = {f.name for f in dataclasses.fields(Patient)}
    assert fields == {"patient_id", "sex", "birth_date"}


def test_identity_fields_are_filled(patients):
    for _, identity in patients:
        assert all(str(v).strip() for v in dataclasses.asdict(identity).values())


def test_everyone_is_an_adult_within_max_age_at_the_start(config, patients):
    ages = [age_on(p.birth_date, config.history.start) for p, _ in patients]
    assert min(ages) >= MIN_AGE
    assert max(ages) < config.max_age


def test_age_mix_matches_the_config(config, patients):
    bands = [b.age_from for b in config.age_mix]
    counts = dict.fromkeys(bands, 0)
    for p, _ in patients:
        age = age_on(p.birth_date, config.history.start)
        counts[max(b for b in bands if b <= age)] += 1
    for band in config.age_mix:
        # With 5,000 patients a share's standard error is at most 0.007.
        assert counts[band.age_from] / N == pytest.approx(band.share, abs=0.025)


def test_sex_mix_matches_the_config(config, patients):
    female = sum(p.sex == "F" for p, _ in patients) / N
    assert female == pytest.approx(config.female_share, abs=0.025)


def test_same_seed_gives_the_same_patients(config):
    assert generate_patients(config, 100) == generate_patients(config, 100)


def test_different_seed_gives_different_patients(config):
    other = config.model_copy(update={"seed": config.seed + 1})
    assert generate_patients(config, 100) != generate_patients(other, 100)


@pytest.mark.parametrize("patient_id", [1, 2, 777, N])
def test_a_patient_does_not_depend_on_other_patients(config, patients, patient_id):
    # Generated alone, a patient is identical to the same patient generated
    # in the full run. So a small run is an exact sample of a large one.
    patient = draw_demographics(config, patient_id)
    identity = draw_identity(Faker(config.locale), config, patient)
    assert (patient, identity) == patients[patient_id - 1]
