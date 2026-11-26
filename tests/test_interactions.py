"""Week 5: the drug-lab events and the RAAS-start cohort find what was planted.

The generator writes what it planted to truth/raas_start.csv. The marts must
find exactly those starts, and, where potassium was measured, exactly those
outcomes. The other rules are planted at rates, so they are checked within
4 standard errors: on the test database, and on the full run's committed
RESULTS.md.
"""

import csv
import datetime as dt
import math
from pathlib import Path

import psycopg
import pytest

from analytics.run import run_query

RESULTS = Path(__file__).resolve().parent.parent / "analytics" / "RESULTS.md"


def within(observed: float, expected: float, n: int) -> bool:
    """A share within 4 standard errors of the expected share."""
    return abs(observed - expected) <= 4 * math.sqrt(expected * (1 - expected) / n)


@pytest.fixture(scope="module")
def truth(dataset, built) -> list[dict]:
    """The planted starts from 2017, with each patient's pseudonym."""
    with psycopg.connect(built) as c:
        pseudonym = dict(
            c.execute("select patient_id, pseudonym from ehr_link.patient_pseudonym")
        )
    with open(dataset / "truth" / "raas_start.csv", encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["start_date"] >= "2017-01-01"]
    for r in rows:
        r["pseudonym"] = pseudonym[int(r["patient_id"])]
        r["start_date"] = dt.date.fromisoformat(r["start_date"])
    return rows


@pytest.fixture(scope="module")
def raas_starts(built) -> list[dict]:
    with psycopg.connect(built) as c:
        cur = c.execute("select * from marts.fact_raas_start")
        names = [d.name for d in cur.description]
        return [dict(zip(names, row, strict=True)) for row in cur.fetchall()]


def test_the_cohort_has_exactly_the_planted_starts(truth, raas_starts):
    planted = {(r["pseudonym"], r["drug_class"], r["start_date"]) for r in truth}
    found = {(s["pseudonym"], s["drug_class"], s["index_date"]) for s in raas_starts}
    assert found == planted
    assert len(found) > 50


def test_measured_outcomes_are_exactly_the_planted_ones(truth, raas_starts):
    # Where two starts' 30-day windows overlap, the earlier start's outcome
    # decides the potassium values in both, so those starts are left out here.
    by_patient: dict[str, list[dt.date]] = {}
    for r in truth:
        by_patient.setdefault(r["pseudonym"], []).append(r["start_date"])
    planted = {
        (r["pseudonym"], r["drug_class"], r["start_date"]): r["hyperkalaemia"] == "true"
        for r in truth
    }
    compared = 0
    for s in raas_starts:
        others = [d for d in by_patient[s["pseudonym"]] if d != s["index_date"]]
        if not s["potassium_measured"] or any(
            abs((d - s["index_date"]).days) <= 30 for d in others
        ):
            continue
        compared += 1
        assert (
            s["hyperkalaemia"]
            == planted[(s["pseudonym"], s["drug_class"], s["index_date"])]
        )
    assert compared > 30


def test_unmeasured_starts_have_no_outcome(raas_starts):
    for s in raas_starts:
        assert (s["hyperkalaemia"] is None) == (not s["potassium_measured"])


def test_the_rule_score_is_one_point_per_item(raas_starts):
    for s in raas_starts:
        points = (
            (s["egfr_before"] is not None and s["egfr_before"] < 45)
            + (s["potassium_before"] is not None and s["potassium_before"] > 5.0)
            + s["combination"]
            + s["diabetes"]
            + (s["age"] >= 75)
        )
        assert s["rule_score"] == points


def test_features_come_from_before_the_index_date(raas_starts):
    # The leakage test, also run by dbt (tests/raas_features_are_known_before_the_index_date.sql).
    for s in raas_starts:
        for column in ("egfr_before_date", "potassium_before_date"):
            if s[column] is not None:
                assert 0 < (s["index_date"] - s[column]).days <= 365


def test_a_triggered_event_breaks_its_rule(built):
    with psycopg.connect(built) as c:
        wrong = c.execute(
            """
            select count(*)
            from marts.fact_drug_lab_event as e
            inner join marts.fact_lab_result as l using (lab_result_key)
            inner join marts.dim_lab_test as t on t.loinc_code = l.loinc_code
            inner join marts.dim_drug_lab_rule as r on r.rule = e.rule and r.test_name = t.test_name
            inner join marts.dim_drug as d on d.atc_code = e.atc_code and d.drug_class = r.drug_class
            where e.rule_triggered <> case r.comparison
                when '>=' then l.value >= r.threshold
                when '>' then l.value > case when r.threshold_times_upper_limit
                    then r.threshold * l.reference_high else r.threshold end
                when '<' then l.value < r.threshold
            end
            """
        ).fetchone()[0]
    assert wrong == 0


@pytest.mark.parametrize(
    "rule", ["hypokalaemia_on_diuretic", "inr_above_4_on_warfarin"]
)
def test_per_test_rules_on_the_test_database(built, rule):
    columns, rows = run_query(built, "q3_drug_lab_interactions.sql")
    row = next(dict(zip(columns, r, strict=True)) for r in rows if r[0] == rule)
    assert row["denominator"] > 200
    assert within(
        row["events"] / row["denominator"],
        float(row["planted_pct"]) / 100,
        row["denominator"],
    )


def committed_q3() -> list[dict]:
    section = (
        RESULTS.read_text(encoding="utf-8").split("## Question 3")[1].split("\n## ")[0]
    )
    lines = [line for line in section.splitlines() if line.startswith("| ")]
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    return [
        dict(zip(header, (c.strip() for c in line.strip("|").split("|")), strict=True))
        for line in lines[2:]
    ]


def test_every_planted_rate_is_found_in_the_full_run():
    # From RESULTS.md, written by `python -m analytics` from the full 40,000-patient run.
    checked = 0
    for row in committed_q3():
        if not row["planted_pct"]:
            continue  # hyperkalaemia: a formula, checked exactly above
        n = int(row["denominator"])
        assert within(int(row["events"]) / n, float(row["planted_pct"]) / 100, n), row[
            "rule"
        ]
        checked += 1
    assert checked == 4
