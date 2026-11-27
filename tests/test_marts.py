"""Pseudonymization and the marts (spec, "Security and compliance deliverables").

- Same input and key -> same pseudonym; a new key -> every pseudonym changes
  and nothing else does.
- No identifier from ehr_identity appears in any mart, and no source key that
  encodes a patient ID.
- The marts reproduce the source, and questions 1, 6 and 7 give the answers
  the generator planted.
"""

import re
from pathlib import Path

import psycopg
import pytest

from analytics.run import PATIENT_COUNTS, run_query, suppress
from generator.config import load_config
from tests.test_database import check_dictionary
from transform.pseudonyms import PREFIX, pseudonym
from transform.run import build
from transform.seeds import SEEDS, seed_files

KEY_A = bytes(range(32))
KEY_B = bytes(range(1, 33))
# Source keys that encode a patient ID, and identity columns: never in a mart.
FORBIDDEN_COLUMNS = {
    "patient_id", "encounter_id", "lab_order_id", "condition_id", "medication_order_id",
    "mrn", "given_name", "family_name", "birth_date", "street_address", "postcode", "city",
}  # fmt: skip


@pytest.fixture(scope="module")
def built(url, loaded):
    build(url, KEY_A)
    return url


def mart_tables(c) -> list[str]:
    rows = c.execute(
        "select table_name from information_schema.tables where table_schema = 'marts' order by 1"
    ).fetchall()
    return [r[0] for r in rows]


# --- The pseudonym function ---


def test_same_id_and_key_give_the_same_pseudonym():
    assert pseudonym(42, KEY_A) == pseudonym(42, KEY_A)
    assert re.fullmatch(r"SYN-P-[0-9a-f]{16}", pseudonym(42, KEY_A))
    assert pseudonym(42, KEY_A).startswith(PREFIX)


def test_a_different_key_or_id_gives_a_different_pseudonym():
    assert pseudonym(42, KEY_A) != pseudonym(42, KEY_B)
    assert pseudonym(42, KEY_A) != pseudonym(43, KEY_A)


def test_seed_files_match_the_config():
    # The reference dimensions are written from the generator's config.
    for name, text in seed_files(load_config()).items():
        assert (SEEDS / name).read_text(encoding="utf-8") == text, name


# --- No identifiers in the marts ---


def test_no_mart_has_an_identifier_or_a_source_key_column(built):
    with psycopg.connect(built) as c:
        columns = c.execute(
            "select table_name || '.' || column_name, column_name "
            "from information_schema.columns where table_schema = 'marts'"
        ).fetchall()
    assert [name for name, column in columns if column in FORBIDDEN_COLUMNS] == []


def test_no_identifier_value_appears_in_any_mart(built):
    with psycopg.connect(built) as c:
        identifiers = set()
        for column in (
            "mrn",
            "given_name",
            "family_name",
            "street_address",
            "postcode",
        ):
            identifiers |= {
                v
                for (v,) in c.execute(
                    f"select {column} from ehr_identity.patient_identity"
                )
            }
        found = {}
        for table in mart_tables(c):
            text_columns = [
                r[0]
                for r in c.execute(
                    "select column_name from information_schema.columns "
                    "where table_schema = 'marts' and table_name = %s and data_type = 'text'",
                    (table,),
                )
            ]
            for column in text_columns:
                values = {
                    v
                    for (v,) in c.execute(
                        f"select distinct {column} from marts.{table}"
                    )
                }
                if hit := values & identifiers:
                    found[f"{table}.{column}"] = sorted(hit)[:3]
    assert found == {}


def test_the_dictionary_lists_exactly_the_mart_and_link_columns(built):
    with psycopg.connect(built) as c:
        check_dictionary(c, ("ehr_link", "marts"))


# --- The marts reproduce the source ---


@pytest.mark.parametrize(
    "mart, source",
    [
        ("dim_patient", "ehr.patient"),
        ("fact_condition", "ehr.condition"),
        ("fact_encounter", "ehr.encounter"),
        ("fact_lab_result", "ehr.lab_result"),
    ],
)
def test_each_mart_has_one_row_per_source_row(built, mart, source):
    with psycopg.connect(built) as c:
        mart_rows = c.execute(f"select count(*) from marts.{mart}").fetchone()[0]
        source_rows = c.execute(f"select count(*) from {source}").fetchone()[0]
    assert mart_rows == source_rows


def test_exposure_periods_cover_exactly_the_ordered_days(built):
    with psycopg.connect(built) as c:
        exposed = c.execute(
            "select sum(days_exposed) from marts.fact_medication_exposure"
        ).fetchone()[0]
        ordered = c.execute(
            "select sum(stop_date - start_date + 1) from ehr.medication_order"
        ).fetchone()[0]
        orders = c.execute(
            "select sum(order_count) from marts.fact_medication_exposure"
        ).fetchone()[0]
        source_orders = c.execute(
            "select count(*) from ehr.medication_order"
        ).fetchone()[0]
    # Orders of one medicine never overlap, so a period's days are its orders' days.
    assert exposed == ordered
    assert orders == source_orders


# --- A new key changes every pseudonym, and nothing else ---


def snapshot(url) -> dict:
    """Each mart's rows, by patient_id (through the link), without pseudonyms or row keys."""
    result = {}
    with psycopg.connect(url) as c:
        links = dict(
            c.execute(
                "select pseudonym, patient_id from ehr_link.patient_pseudonym"
            ).fetchall()
        )
        result["pseudonyms"] = {v: k for k, v in links.items()}
        for table in ("dim_patient", "fact_condition", "fact_encounter", "fact_lab_result",
                      "fact_medication_exposure"):  # fmt: skip
            cur = c.execute(f"select * from marts.{table}")
            names = [d.name for d in cur.description]
            rows = []
            for row in cur.fetchall():
                record = dict(zip(names, row, strict=True))
                patient = links[record.pop("pseudonym")]
                for name in names:
                    if name.endswith("_key") and not name.endswith("date_key"):
                        record.pop(
                            name, None
                        )  # row keys are numbered in pseudonym order
                rows.append(
                    (patient, tuple(sorted(record.items(), key=lambda kv: kv[0])))
                )
            result[table] = sorted(rows, key=repr)
    return result


def test_a_new_key_changes_every_pseudonym_and_nothing_else(built):
    before = snapshot(built)
    try:
        build(built, KEY_B)
        after = snapshot(built)
    finally:
        build(built, KEY_A)
    changed = [
        p
        for p in before["pseudonyms"]
        if before["pseudonyms"][p] != after["pseudonyms"][p]
    ]
    assert len(changed) == len(before["pseudonyms"])
    for table in before:
        if table != "pseudonyms":
            assert before[table] == after[table], table


# --- Questions 1, 6 and 7 ---


def test_question_1_counts_match_the_source(built):
    columns, rows = run_query(built, "q1a_cohort_sizes.sql")
    i = {name: n for n, name in enumerate(columns)}
    with psycopg.connect(built) as c:
        for condition, code in [("hypertension", "I10"), ("heart_failure", "I50")]:
            expected = c.execute(
                "select count(*) from ehr.condition where icd10_code = %s and onset_date < '2016-01-01'",
                (code,),
            ).fetchone()[0]
            counted = sum(
                r[i["with_condition"]] for r in rows if r[i["condition"]] == condition
            )
            assert counted == expected, condition
        patients = c.execute("select count(*) from ehr.patient").fetchone()[0]
    assert sum(r[i["patients"]] for r in rows if r[i["condition"]] == "ckd") == patients


def test_question_6_hba1c_falls_after_metformin(built):
    columns, rows = run_query(built, "q6_hba1c_after_metformin.sql")
    result = dict(zip(columns, rows[0], strict=True))
    assert result["with_hba1c_before_and_after"] >= 5
    # The generator plants a fall of 10 mmol/mol at full effect.
    assert result["mean_change"] < -5


def test_question_7_finds_no_data_quality_problems(built):
    _, rows = run_query(built, "q7_data_quality.sql")
    assert len(rows) == 10
    assert {name: n for name, n in rows if n != 0} == {}


# --- Small-cell suppression in what reaches the repository ---


def test_small_patient_counts_are_suppressed_with_what_they_give_away():
    columns = ["condition", "patients", "with_condition", "prevalence_pct"]
    assert suppress(columns, ("ckd", 120, 7, 5.8)) == ["ckd", "120", "<10", "<10"]
    assert suppress(columns, ("ckd", 120, 0, 0.0)) == ["ckd", "120", "0", "0.0"]
    assert suppress(columns, ("ckd", 120, 10, 8.3)) == ["ckd", "120", "10", "8.3"]


def test_the_committed_results_have_no_small_patient_count():
    results = (
        Path(__file__).resolve().parent.parent / "analytics" / "RESULTS.md"
    ).read_text(encoding="utf-8")
    for table in results.split("\n## ")[1:]:
        lines = [line for line in table.splitlines() if line.startswith("| ")]
        if not lines:
            continue
        header = [c.strip() for c in lines[0].strip("|").split("|")]
        for line in lines[2:]:
            cells = dict(
                zip(
                    header, (c.strip() for c in line.strip("|").split("|")), strict=True
                )
            )
            for column in PATIENT_COUNTS & set(header):
                value = cells[column]
                assert value == "<10" or int(value) == 0 or int(value) >= 10, (
                    column,
                    value,
                )
