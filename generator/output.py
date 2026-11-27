"""Write the generated dataset as CSV files, with a SHA-256 manifest.

One file per table of the `ehr` schema, and the identity table in its own
folder, `ehr_identity/`, because only the identity schema may hold
identifiers. Rows and columns are written in a fixed order with fixed
formatting, so the same seed, config and locked dependencies give
byte-identical files, and so an identical manifest.
"""

import csv
import datetime as dt
import hashlib
from pathlib import Path

from generator.conditions import draw_history
from generator.config import Config
from generator.patients import generate_patients
from generator.visits import VisitMaker

MANIFEST = "manifest.sha256"

COLUMNS = {
    "ehr_identity/patient_identity.csv": [
        "patient_id", "mrn", "given_name", "family_name", "birth_date", "sex",
        "street_address", "postcode", "city", "province",
    ],
    "patient.csv": ["patient_id", "sex", "birth_year", "death_date"],
    "department.csv": ["department_id", "code", "name"],
    "clinician.csv": ["clinician_id", "department_id", "given_name", "family_name"],
    "icd10_code.csv": ["code"],
    "condition.csv": ["condition_id", "patient_id", "icd10_code", "onset_date", "resolved_date"],
    "encounter.csv": [
        "encounter_id", "patient_id", "department_id", "clinician_id",
        "encounter_type", "start_time", "end_time",
    ],
    "encounter_diagnosis.csv": ["encounter_id", "icd10_code", "is_primary"],
}  # fmt: skip

# Condition IDs are patient_id * this + a counter, like encounter IDs.
CONDITIONS_PER_PATIENT_MAX = 100


def cell(value) -> str:
    """One fixed text form per type, so output never depends on the platform."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)


class Tables:
    """Open CSV writers, one per table, each with its header written."""

    def __init__(self, out_dir: Path):
        self.files, self.writers, self.counts = {}, {}, {}
        for name, columns in COLUMNS.items():
            path = out_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            # newline="" and "\n" endings: the same bytes on Windows and Linux.
            f = open(path, "w", encoding="utf-8", newline="")  # noqa: SIM115
            self.files[name] = f
            self.writers[name] = csv.writer(f, lineterminator="\n")
            self.writers[name].writerow(columns)
            self.counts[name] = 0

    def write(self, name: str, *values) -> None:
        assert len(values) == len(COLUMNS[name]), name
        self.writers[name].writerow([cell(v) for v in values])
        self.counts[name] += 1

    def close(self) -> None:
        for f in self.files.values():
            f.close()


def write_manifest(out_dir: Path) -> Path:
    """`sha256sum` format, so `sha256sum -c manifest.sha256` checks it."""
    lines = []
    for name in sorted(COLUMNS):
        digest = hashlib.sha256((out_dir / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}\n")
    path = out_dir / MANIFEST
    path.write_text("".join(lines), encoding="utf-8", newline="")
    return path


def write_dataset(
    config: Config, out_dir: Path, population: int | None = None
) -> dict[str, int]:
    """Generate everything and write it to `out_dir`. Returns row counts per table."""
    out_dir.mkdir(parents=True, exist_ok=True)
    visit_maker = VisitMaker(config)
    tables = Tables(out_dir)
    try:
        for d in visit_maker.departments:
            tables.write("department.csv", d.department_id, d.code, d.name)
        for c in visit_maker.clinicians:
            tables.write(
                "clinician.csv",
                c.clinician_id,
                c.department_id,
                c.given_name,
                c.family_name,
            )
        for condition in config.conditions.values():
            tables.write("icd10_code.csv", condition.icd10)

        for patient, identity in generate_patients(config, population):
            history = draw_history(config, patient)
            tables.write(
                "ehr_identity/patient_identity.csv", identity.patient_id, identity.mrn,
                identity.given_name, identity.family_name, identity.birth_date, identity.sex,
                identity.street_address, identity.postcode, identity.city, identity.province,
            )  # fmt: skip
            # The clinical table keeps only the birth year (data minimisation).
            tables.write(
                "patient.csv", patient.patient_id, patient.sex,
                patient.birth_date.year, history.death_date,
            )  # fmt: skip
            for k, record in enumerate(history.conditions, start=1):
                condition_id = patient.patient_id * CONDITIONS_PER_PATIENT_MAX + k
                tables.write(
                    "condition.csv", condition_id, patient.patient_id, record.icd10,
                    record.onset, None,  # chronic: none of the six resolve
                )  # fmt: skip
            encounters, diagnoses = visit_maker.draw(patient, history)
            for e in encounters:
                tables.write(
                    "encounter.csv", e.encounter_id, e.patient_id, e.department_id,
                    e.clinician_id, e.encounter_type, e.start, e.end,
                )  # fmt: skip
            for d in diagnoses:
                tables.write(
                    "encounter_diagnosis.csv", d.encounter_id, d.icd10, d.is_primary
                )
    finally:
        tables.close()
    write_manifest(out_dir)
    return dict(tables.counts)
