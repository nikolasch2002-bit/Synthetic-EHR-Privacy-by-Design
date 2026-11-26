"""The written dataset: reproducible to the byte, and identifiers in one place only."""

import csv
import hashlib

import pytest

from generator.config import load_config
from generator.output import COLUMNS, MANIFEST, write_dataset

N = 100
IDENTITY = "ehr_identity/patient_identity.csv"
# A patient's direct identifiers.
IDENTIFIER_COLUMNS = {"mrn", "birth_date", "street_address", "postcode", "city"}
NAME_COLUMNS = {"given_name", "family_name"}
# Clinicians are staff, not patients: the spec gives them a (fake) name.
NAMES_ALLOWED = {IDENTITY, "clinician.csv"}


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def dataset(config, tmp_path_factory):
    out = tmp_path_factory.mktemp("data")
    counts = write_dataset(config, out, N)
    return out, counts


def read(out, name) -> list[dict]:
    with open(out / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_same_seed_gives_the_same_manifest(config, dataset, tmp_path):
    out, _ = dataset
    write_dataset(config, tmp_path, N)
    assert (tmp_path / MANIFEST).read_bytes() == (out / MANIFEST).read_bytes()


def test_different_seed_gives_a_different_manifest(config, dataset, tmp_path):
    out, _ = dataset
    write_dataset(config.model_copy(update={"seed": config.seed + 1}), tmp_path, N)
    assert (tmp_path / MANIFEST).read_bytes() != (out / MANIFEST).read_bytes()


def test_manifest_lists_every_file_with_its_hash(dataset):
    out, _ = dataset
    lines = (out / MANIFEST).read_text(encoding="utf-8").splitlines()
    listed = {}
    for line in lines:
        digest, name = line.split("  ")
        listed[name] = digest
    assert set(listed) == set(COLUMNS)
    for name, digest in listed.items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest


def test_every_file_has_its_header_and_row_count(dataset):
    out, counts = dataset
    for name, columns in COLUMNS.items():
        with open(out / name, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        assert rows[0] == columns
        assert len(rows) - 1 == counts[name]


def test_identifiers_appear_only_in_the_identity_table(dataset):
    out, _ = dataset
    mrns = {row["mrn"] for row in read(out, IDENTITY)}
    for name, columns in COLUMNS.items():
        if name == IDENTITY:
            continue
        assert not IDENTIFIER_COLUMNS & set(columns), name
        if name not in NAMES_ALLOWED:
            assert not NAME_COLUMNS & set(columns), name
        text = (out / name).read_text(encoding="utf-8")
        assert "SYN-" not in text, name  # no MRN copied into a clinical table
    assert len(mrns) == N


def test_clinical_patient_table_keeps_only_the_birth_year(dataset):
    out, _ = dataset
    identity = {r["patient_id"]: r for r in read(out, IDENTITY)}
    for row in read(out, "patient.csv"):
        assert row["birth_year"] == identity[row["patient_id"]]["birth_date"][:4]


def test_every_reference_points_to_an_existing_row(dataset):
    out, _ = dataset
    patients = {r["patient_id"] for r in read(out, "patient.csv")}
    departments = {r["department_id"] for r in read(out, "department.csv")}
    clinicians = {r["clinician_id"] for r in read(out, "clinician.csv")}
    codes = {r["code"] for r in read(out, "icd10_code.csv")}
    encounters = read(out, "encounter.csv")
    assert {r["patient_id"] for r in read(out, IDENTITY)} == patients
    assert all(
        r["patient_id"] in patients and r["icd10_code"] in codes
        for r in read(out, "condition.csv")
    )
    assert all(
        e["patient_id"] in patients
        and e["department_id"] in departments
        and e["clinician_id"] in clinicians
        for e in encounters
    )
    ids = {e["encounter_id"] for e in encounters}
    assert len(ids) == len(encounters)
    assert all(
        d["encounter_id"] in ids and d["icd10_code"] in codes
        for d in read(out, "encounter_diagnosis.csv")
    )


def test_icd10_codes_are_bare_codes_without_titles(dataset):
    # The WHO's titles wait for its written answer (spec, "Data").
    out, _ = dataset
    assert COLUMNS["icd10_code.csv"] == ["code"]
    assert {r["code"] for r in read(out, "icd10_code.csv")} == {
        "I10",
        "E78",
        "E11",
        "N18",
        "I48",
        "I50",
    }


def test_atc_and_loinc_codes_are_bare_codes_without_names(dataset):
    # Names wait until the owner has read the ATC and LOINC terms (spec, "Data").
    _, counts = dataset
    assert COLUMNS["atc_code.csv"] == ["code"]
    assert COLUMNS["loinc_code.csv"] == ["code"]
    assert counts["atc_code.csv"] == 11
    assert counts["loinc_code.csv"] == 10
