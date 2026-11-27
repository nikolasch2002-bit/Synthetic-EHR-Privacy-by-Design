"""The ehr schemas in Postgres: the data loads, constraints hold, the dictionary matches.

The database fixtures (url, dataset, loaded, conn) are in conftest.py.
"""

import re
import shutil
from pathlib import Path

import psycopg
import pytest
from psycopg import errors

from generator.output import COLUMNS, write_manifest
from loader.load import TABLES, ManifestError, load

DICTIONARY = (
    Path(__file__).resolve().parent.parent / "governance" / "data-dictionary.md"
)


def csv_rows(path: Path) -> int:
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


def test_every_table_loads_every_row(dataset, loaded):
    for name, table in TABLES.items():
        assert loaded[table] == csv_rows(dataset / name), table


# --- Constraints: each bad row must be refused ---

PATIENT = "(select min(patient_id) from ehr.patient)"
OTHER_PATIENT = "(select max(patient_id) from ehr.patient)"
ENCOUNTER = "(select min(encounter_id) from ehr.encounter)"

BAD_ROWS = {
    "visit ends before it starts": (
        errors.CheckViolation,
        (
            f"insert into ehr.encounter select 1, {PATIENT}, 1, c.clinician_id, 'outpatient', "
            "'2020-01-02 10:00', '2020-01-02 09:00' from ehr.clinician c where c.department_id = 1 limit 1"
        ),
    ),
    "unknown visit type": (
        errors.CheckViolation,
        (
            f"insert into ehr.encounter select 1, {PATIENT}, 1, c.clinician_id, 'telepathy', "
            "'2020-01-02 10:00', '2020-01-02 11:00' from ehr.clinician c where c.department_id = 1 limit 1"
        ),
    ),
    "clinician from another department": (
        errors.ForeignKeyViolation,
        (
            f"insert into ehr.encounter select 1, {PATIENT}, 1, c.clinician_id, 'outpatient', "
            "'2020-01-02 10:00', '2020-01-02 11:00' from ehr.clinician c where c.department_id = 2 limit 1"
        ),
    ),
    "MRN without the SYN- prefix": (
        errors.CheckViolation,
        f"update ehr_identity.patient_identity set mrn = '123456789' where patient_id = {PATIENT}",
    ),
    "sex other than F or M": (
        errors.CheckViolation,
        f"update ehr.patient set sex = 'X' where patient_id = {PATIENT}",
    ),
    "death before birth": (
        errors.CheckViolation,
        f"update ehr.patient set death_date = make_date(birth_year - 1, 1, 1) where patient_id = {PATIENT}",
    ),
    "a condition twice on one problem list": (
        errors.UniqueViolation,
        (
            "insert into ehr.condition select condition_id + 99, patient_id, icd10_code, onset_date, null "
            "from ehr.condition limit 1"
        ),
    ),
    "a code not in the code table": (
        errors.ForeignKeyViolation,
        f"insert into ehr.condition values (1, {PATIENT}, 'Z99', '2020-01-01', null)",
    ),
    "a second primary diagnosis at one visit": (
        errors.UniqueViolation,
        (
            "insert into ehr.encounter_diagnosis select d.encounter_id, c.code, true "
            "from ehr.encounter_diagnosis d cross join ehr.icd10_code c where d.is_primary "
            "and not exists (select 1 from ehr.encounter_diagnosis x where x.encounter_id = d.encounter_id "
            "and x.icd10_code = c.code) limit 1"
        ),
    ),
    "a lab order on another patient's visit": (
        errors.ForeignKeyViolation,
        (
            f"insert into ehr.lab_order select 1, {OTHER_PATIENT}, {ENCOUNTER}, '2823-3', now() "
            f"where {OTHER_PATIENT} <> (select patient_id from ehr.encounter where encounter_id = {ENCOUNTER})"
        ),
    ),
    "a dose of zero": (
        errors.CheckViolation,
        (
            "update ehr.medication_order set dose = 0 where medication_order_id = "
            "(select min(medication_order_id) from ehr.medication_order)"
        ),
    ),
    "an order stopping before it starts": (
        errors.CheckViolation,
        (
            "update ehr.medication_order set stop_date = start_date - 1 where medication_order_id = "
            "(select min(medication_order_id) from ehr.medication_order)"
        ),
    ),
    "a reference range upside down": (
        errors.CheckViolation,
        (
            "update ehr.lab_result set reference_low = 10, reference_high = 1 where lab_order_id = "
            "(select min(lab_order_id) from ehr.lab_result)"
        ),
    ),
}


@pytest.mark.parametrize("error, sql", BAD_ROWS.values(), ids=BAD_ROWS.keys())
def test_a_bad_row_is_refused(conn, error, sql):
    with pytest.raises(error):
        conn.execute(sql)


# --- What the constraints cannot see, checked by query ---


def test_birth_year_matches_the_identity_birth_date(conn):
    mismatches = conn.execute(
        "select count(*) from ehr.patient p join ehr_identity.patient_identity i using (patient_id) "
        "where p.birth_year <> extract(year from i.birth_date)"
    ).fetchone()[0]
    assert mismatches == 0


def test_lab_results_are_reported_after_they_are_ordered(conn):
    early = conn.execute(
        "select count(*) from ehr.lab_result r join ehr.lab_order o using (lab_order_id) "
        "where r.resulted_at < o.ordered_at"
    ).fetchone()[0]
    assert early == 0


# --- The loader ---


def test_the_loader_refuses_files_that_do_not_match_the_manifest(
    url, dataset, tmp_path, loaded
):
    copy = tmp_path / "data"
    shutil.copytree(dataset, copy)
    path = copy / "patient.csv"
    path.write_bytes(path.read_bytes().replace(b",F,", b",M,", 1))
    with pytest.raises(ManifestError):
        load(copy, url)


def test_a_failed_load_leaves_the_database_as_it_was(url, dataset, tmp_path, loaded):
    # A file that matches its (rewritten) manifest but breaks a constraint:
    # the load fails part-way, inside its one transaction.
    copy = tmp_path / "data"
    shutil.copytree(dataset, copy)
    path = copy / "encounter.csv"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    lines.append(lines[1])  # a duplicate primary key
    path.write_text("".join(lines), encoding="utf-8", newline="")
    write_manifest(copy)
    with pytest.raises(errors.UniqueViolation):
        load(copy, url)
    with psycopg.connect(url) as c:
        assert (
            c.execute("select count(*) from ehr.encounter").fetchone()[0]
            == loaded["ehr.encounter"]
        )


# --- The data dictionary ---

TYPES = {"character": "char(1)", "timestamp without time zone": "timestamp"}


def dictionary_columns(schemas: tuple[str, ...]) -> dict[str, str]:
    """`schema.table.column` -> type, from governance/data-dictionary.md."""
    columns, table = {}, None
    for line in DICTIONARY.read_text(encoding="utf-8").splitlines():
        if heading := re.match(r"^### `([a-z_]+\.[a-z0-9_]+)`", line):
            table = heading.group(1)
        elif line.startswith("### "):
            table = None  # a section whose rows name their own table
        elif row := re.match(r"^\| `([a-z0-9_.]+)` \| ([a-z0-9()]+) \|", line):
            name, kind = row.groups()
            columns[name if name.count(".") == 2 else f"{table}.{name}"] = kind
    return {k: v for k, v in columns.items() if k.split(".")[0] in schemas}


def check_dictionary(conn, schemas: tuple[str, ...]) -> None:
    """The dictionary lists exactly the columns of `schemas`, with their types."""
    rows = conn.execute(
        "select table_schema || '.' || table_name || '.' || column_name, data_type "
        "from information_schema.columns where table_schema = any(%s)",
        (list(schemas),),
    ).fetchall()
    database = {name: TYPES.get(kind, kind) for name, kind in rows}
    documented = dictionary_columns(schemas)
    assert sorted(set(database) - set(documented)) == [], (
        "in the database, not in the dictionary"
    )
    assert sorted(set(documented) - set(database)) == [], (
        "in the dictionary, not in the database"
    )
    assert {k: v for k, v in documented.items() if database[k] != v} == {}, (
        "types differ"
    )


SOURCE_SCHEMAS = ("ehr", "ehr_identity")


def test_the_dictionary_lists_exactly_the_database_columns_with_their_types(conn):
    check_dictionary(conn, SOURCE_SCHEMAS)


def test_the_dictionary_covers_every_generated_table():
    tables = {name.rsplit(".", 1)[0] for name in dictionary_columns(SOURCE_SCHEMAS)}
    assert tables == set(TABLES.values())
    assert set(TABLES) <= set(COLUMNS)
