"""Load a generated dataset into PostgreSQL: rebuild the schemas, then COPY.

The dataset's manifest is checked first, so only files exactly as the
generator wrote them are loaded. Everything runs in one transaction: a
failed load leaves the database as it was.
"""

import hashlib
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from generator.output import COLUMNS, MANIFEST

SCHEMA_SQL = Path(__file__).resolve().parent.parent / "db" / "ehr_schema.sql"

# CSV file -> table, in an order that respects the foreign keys.
TABLES = {
    "icd10_code.csv": "ehr.icd10_code",
    "atc_code.csv": "ehr.atc_code",
    "loinc_code.csv": "ehr.loinc_code",
    "patient.csv": "ehr.patient",
    "ehr_identity/patient_identity.csv": "ehr_identity.patient_identity",
    "department.csv": "ehr.department",
    "clinician.csv": "ehr.clinician",
    "condition.csv": "ehr.condition",
    "encounter.csv": "ehr.encounter",
    "encounter_diagnosis.csv": "ehr.encounter_diagnosis",
    "medication_order.csv": "ehr.medication_order",
    "lab_order.csv": "ehr.lab_order",
    "lab_result.csv": "ehr.lab_result",
}
# Written by the generator but never loaded: what was planted, for tests only.
NOT_LOADED = {"truth/raas_start.csv"}


class ManifestError(Exception):
    pass


def database_url() -> str:
    """DATABASE_URL from the environment, or from .env. Never printed."""
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see README, 'Run the database')")
    return url


def check_manifest(data_dir: Path) -> None:
    """Every file matches its SHA-256 in the manifest, and every file is listed."""
    listed = {}
    for line in (data_dir / MANIFEST).read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        listed[name] = digest
    if set(listed) != set(COLUMNS):
        raise ManifestError("the manifest does not list exactly the generator's files")
    for name, digest in listed.items():
        if hashlib.sha256((data_dir / name).read_bytes()).hexdigest() != digest:
            raise ManifestError(f"{name} does not match the manifest")


def load(data_dir: Path, url: str) -> dict[str, int]:
    """Rebuild the schemas and load every table. Returns rows per table."""
    check_manifest(data_dir)
    assert set(TABLES) | NOT_LOADED == set(COLUMNS), (
        "a generated table has no loader entry"
    )
    counts = {}
    with psycopg.connect(url) as conn:  # one transaction; commits on success
        conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
        for name, table in TABLES.items():
            columns = ", ".join(COLUMNS[name])
            # COPY ... CSV HEADER: empty fields become NULL.
            sql = f"copy {table} ({columns}) from stdin with (format csv, header true)"
            with (
                conn.cursor() as cur,
                cur.copy(sql) as copy,
                open(data_dir / name, "rb") as f,
            ):
                while chunk := f.read(1 << 20):
                    copy.write(chunk)
            counts[table] = conn.execute(f"select count(*) from {table}").fetchone()[0]
        conn.execute("analyze")
    return counts
