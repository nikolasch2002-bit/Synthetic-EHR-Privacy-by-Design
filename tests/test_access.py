"""Week 7: roles, row-level security, suppression, audit, and the publish step.

Each test takes on a role with SET ROLE, in its own connection, and checks
what it can and cannot read against governance/access-control.md, cell by
cell. Failing-then-passing: each control was shown to fail without it (PR).
"""

from pathlib import Path

import psycopg
import pytest

from generator.config import load_config
from ml.run import PREDICTIONS_SQL
from publish.publish import PublishRefused, hosted_contents, publish
from tests.test_database import check_dictionary

MATRIX = Path(__file__).resolve().parent.parent / "governance" / "access-control.md"
# One table stands for each object in the matrix.
OBJECT_TABLE = {
    "ehr": "ehr.patient",
    "ehr_identity": "ehr_identity.patient_identity",
    "ehr_link": "ehr_link.patient_pseudonym",
    "marts": "marts.dim_patient",
    "ml": "ml.raas_start_prediction",
    "marts_public": "marts_public.public_rule_score",
    "security.relink_log": "security.relink_log",
}
CLINICIANS = [f"clinician_{d}" for d in load_config().departments]
REFUSED = "refused"


@pytest.fixture(scope="module")
def db(built) -> str:
    """The test database with marts built and the predictions table present."""
    with psycopg.connect(built) as c:
        c.execute(PREDICTIONS_SQL)
    return built


def as_role(url: str, role: str, sql: str, *params):
    """Run one query as `role`, in its own connection: a refused query cannot
    leave the next one running as someone else."""
    with psycopg.connect(url, autocommit=True) as c:
        c.execute(f"set role {role}")
        try:
            return c.execute(sql, params).fetchone()[0]
        except psycopg.errors.InsufficientPrivilege:
            return REFUSED


def as_admin(url: str, sql: str, *params):
    with psycopg.connect(url) as c:
        return c.execute(sql, params).fetchone()[0]


def cells(line: str) -> list[str]:
    return [c.strip().strip("`") for c in line.strip().strip("|").split("|")]


def matrix() -> dict[str, dict[str, str]]:
    """role -> object -> cell, from the matrix table in governance/access-control.md."""
    lines = MATRIX.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("| Role | `ehr`"))
    objects = cells(lines[start])[1:]
    result = {}
    for line in lines[start + 2 :]:  # skip the header and its "| --- |" line
        if not line.startswith("|"):
            break
        role, *row = cells(line)
        result[role] = dict(zip(objects, row, strict=True))
    return result


def own_patients(url: str, role: str) -> int:
    department = role.removeprefix("clinician_")
    return as_admin(
        url,
        "select count(distinct e.patient_id) from ehr.encounter as e "
        "inner join ehr.department as d using (department_id) where d.code = %s",
        department,
    )


def test_the_roles_are_those_in_the_matrix(db):
    roles = set(matrix())
    assert roles == {
        "clinician_<dept>",
        "researcher",
        "data_steward",
        "public_app",
        "etl",
    }
    with psycopg.connect(db) as c:
        existing = {r[0] for r in c.execute("select rolname from pg_roles")}
    assert set(CLINICIANS) | (roles - {"clinician_<dept>"}) <= existing


def cases():
    for role, row in matrix().items():
        for role_name in CLINICIANS if role == "clinician_<dept>" else [role]:
            for obj, cell in row.items():
                yield pytest.param(role_name, obj, cell, id=f"{role_name}-{obj}")


@pytest.mark.parametrize("role, obj, cell", list(cases()))
def test_each_role_reads_exactly_its_cell_of_the_matrix(db, role, obj, cell):
    table = OBJECT_TABLE[obj]
    seen = as_role(db, role, f"select count(*) from {table}")
    everything = as_admin(db, f"select count(*) from {table}")
    if cell == "none":
        assert seen == REFUSED
    elif cell in ("all", "read, insert"):
        assert seen == everything
    elif cell == "own patients":
        assert seen == own_patients(db, role) < everything
    else:
        pytest.fail(f"unknown cell {cell!r}")


# --- Row-level security: the full record of a clinician's own patients ---


@pytest.mark.parametrize("role", CLINICIANS)
def test_a_clinician_sees_the_full_record_of_its_patients_and_nothing_else(db, role):
    department = role.removeprefix("clinician_")
    mine = (
        "select patient_id from ehr.encounter as e inner join ehr.department as d "
        "using (department_id) where d.code = %s"
    )
    # Every table, including those keyed to a visit or an order.
    for table, key in [
        ("ehr.encounter", "patient_id"),
        ("ehr.condition", "patient_id"),
        ("ehr.medication_order", "patient_id"),
        ("ehr.lab_order", "patient_id"),
    ]:
        expected = as_admin(
            db, f"select count(*) from {table} where {key} in ({mine})", department
        )
        assert as_role(db, role, f"select count(*) from {table}") == expected, table
    expected = as_admin(
        db,
        f"select count(*) from ehr.lab_result as r inner join ehr.lab_order as o using (lab_order_id) "
        f"where o.patient_id in ({mine})",
        department,
    )
    assert as_role(db, role, "select count(*) from ehr.lab_result") == expected
    # The full record: visits in other departments too, for its own patients.
    other_departments = as_role(
        db, role,
        "select count(*) from ehr.encounter as e inner join ehr.department as d using (department_id) "
        "where d.code <> %s", department,
    )  # fmt: skip
    assert other_departments > 0


def test_a_clinician_cannot_read_another_departments_care_relations(db):
    assert (
        as_role(
            db,
            CLINICIANS[0],
            "select count(*) from security.care_relation where role_name <> current_user",
        )
        == 0
    )


# --- The audit log ---


def test_a_relink_returns_the_identity_and_adds_a_log_row(db):
    with psycopg.connect(db) as c:
        pseudonym, mrn = c.execute(
            "select l.pseudonym, i.mrn from ehr_link.patient_pseudonym as l "
            "inner join ehr_identity.patient_identity as i using (patient_id) limit 1"
        ).fetchone()
    before = as_admin(db, "select count(*) from security.relink_log")
    with psycopg.connect(db, autocommit=True) as c:
        c.execute("set role data_steward")
        found = c.execute(
            "select mrn from security.relink(%s)", (pseudonym,)
        ).fetchone()[0]
    assert found == mrn
    assert as_admin(db, "select count(*) from security.relink_log") == before + 1
    who = as_admin(
        db,
        "select relinked_by from security.relink_log order by relink_id desc limit 1",
    )
    assert who == "data_steward"


@pytest.mark.parametrize(
    "sql",
    [
        "delete from security.relink_log",
        "update security.relink_log set pseudonym = 'x'",
    ],
)
def test_the_steward_cannot_change_or_delete_the_log(db, sql):
    with psycopg.connect(db, autocommit=True) as c:
        c.execute("set role data_steward")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute(sql)


@pytest.mark.parametrize("role", ["researcher", "etl", "public_app", *CLINICIANS])
def test_no_one_but_the_steward_can_relink(db, role):
    with psycopg.connect(db, autocommit=True) as c:
        c.execute(f"set role {role}")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("select * from security.relink('SYN-P-0000000000000000')")


# --- Small-cell suppression ---


def test_every_count_below_k_is_suppressed_in_the_public_layer(db):
    k = 10
    with psycopg.connect(db) as c:
        public = c.execute(
            "select condition, age_band, sex, patients, is_suppressed from marts_public.public_condition_count"
        ).fetchall()
        true_counts = {
            (condition, band, sex): n
            for condition, band, sex, n in c.execute(
                """
                select c.condition, d.age_band_at_start, d.sex, count(*) filter (where c.present)
                from marts.dim_patient as d
                cross join lateral (values
                    ('hypertension', d.hypertension_at_start), ('hyperlipidaemia', d.hyperlipidaemia_at_start),
                    ('type2_diabetes', d.type2_diabetes_at_start), ('ckd', d.ckd_at_start),
                    ('atrial_fibrillation', d.atrial_fibrillation_at_start),
                    ('heart_failure', d.heart_failure_at_start)
                ) as c (condition, present)
                group by 1, 2, 3
                """
            ).fetchall()
        }
    suppressed = 0
    for condition, band, sex, patients, is_suppressed in public:
        truth = true_counts[(condition, band, sex)]
        if truth < k:
            assert patients is None and is_suppressed
            suppressed += 1
        else:
            assert patients == truth and not is_suppressed
    assert suppressed > 0  # the test data has small cells, so the rule is exercised


def test_no_public_table_publishes_a_small_count(db):
    with psycopg.connect(db) as c:
        rows = c.execute(
            "select table_name, column_name from information_schema.columns "
            "where table_schema = 'marts_public' and data_type = 'bigint'"
        ).fetchall()
        for table, column in rows:
            small = c.execute(
                f"select count(*) from marts_public.{table} where {column} < 10"
            ).fetchone()[0]
            assert small == 0, f"{table}.{column}"


# --- The publish step ---


@pytest.fixture
def stand_in(db) -> str:
    """A fresh, empty database standing in for the hosted one."""
    name = db.rsplit("/", 1)[1] + "_hosted"
    with psycopg.connect(db, autocommit=True) as c:
        c.execute(f'drop database if exists "{name}"')
        c.execute(f'create database "{name}"')
    return db.rsplit("/", 1)[0] + "/" + name


def test_after_publishing_the_hosted_database_holds_only_marts_public(db, stand_in):
    counts = publish(db, stand_in)
    with psycopg.connect(stand_in) as c:
        contents = hosted_contents(c)
    assert contents, "nothing was published"
    assert {schema for schema, _, _ in contents} == {"marts_public"}
    with psycopg.connect(db) as c:
        for table, rows in counts.items():
            assert (
                rows
                == c.execute(f"select count(*) from marts_public.{table}").fetchone()[0]
            )


def test_the_public_app_can_read_what_was_published(db, stand_in):
    publish(db, stand_in)
    assert (
        as_role(
            stand_in,
            "public_app",
            "select count(*) from marts_public.public_rule_score",
        )
        > 0
    )


def test_publishing_refuses_a_target_that_holds_anything_else(db, stand_in):
    with psycopg.connect(stand_in) as c:
        c.execute("create table public.leftover (id int)")
    with pytest.raises(PublishRefused):
        publish(db, stand_in)


# --- The data dictionary covers the new schemas ---


def test_the_dictionary_lists_the_public_and_security_columns(db):
    with psycopg.connect(db) as c:
        check_dictionary(c, ("marts_public", "security"))
