"""Run the question files and write their results to RESULTS.md.

Every number in RESULTS.md comes from this run: nothing is typed by hand.
"""

from pathlib import Path

import psycopg

HERE = Path(__file__).resolve().parent

TITLES = {
    "q1a_cohort_sizes.sql": "Question 1a: patients with each condition, by age band and sex (on 2016-01-01)",
    "q1b_combinations.sql": "Question 1b: the 15 most common combinations of conditions (on 2016-01-01)",
    "q3_drug_lab_interactions.sql": "Question 3: each drug-lab rule, found against planted",
    "q5_rule_score.sql": "Question 5 (rule baseline): hyperkalaemia after a RAAS-inhibitor start, by rule score",
    "q6_hba1c_after_metformin.sql": "Question 6: HbA1c before and after metformin starts (mmol/mol)",
    "q7_data_quality.sql": "Question 7: data quality checks (every count should be 0)",
}


def run_query(url: str, name: str) -> tuple[list[str], list[tuple]]:
    sql = (HERE / name).read_text(encoding="utf-8")
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [c.name for c in cur.description], cur.fetchall()


# Small-cell suppression (spec, "Data": aggregates reach the repository only
# after it). A count of patients from 1 to K - 1 is shown as "<10", and so is
# a percentage computed from such a count, which would give it away.
K = 10
PATIENT_COUNTS = {
    "patients",
    "with_condition",
    "metformin_starts",
    "with_hba1c_before_and_after",
    "denominator",
    "events",
    "starts",
}
FROM_COUNT = {
    "prevalence_pct": "with_condition",
    "share_pct": "patients",
    "rate_pct": "events",
    "event_rate_pct": "events",
}


def suppress(columns: list[str], row: tuple) -> list[str]:
    values = dict(zip(columns, row, strict=True))
    small = {
        c
        for c in PATIENT_COUNTS & set(columns)
        if values[c] is not None and 0 < values[c] < K
    }
    cells = []
    for column, value in values.items():
        if column in small or FROM_COUNT.get(column) in small:
            cells.append(f"<{K}")
        else:
            cells.append("" if value is None else str(value))
    return cells


def markdown_table(columns: list[str], rows: list[tuple]) -> str:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines += ["| " + " | ".join(suppress(columns, row)) + " |" for row in rows]
    return "\n".join(lines)


def write_results(url: str, path: Path = HERE / "RESULTS.md") -> None:
    with psycopg.connect(url) as conn:
        patients = conn.execute("select count(*) from marts.dim_patient").fetchone()[0]
    parts = [
        "# Results",
        "",
        (
            f"Written by `python -m analytics` from the marts: {patients:,} patients, "
            "generated from the seed in `config/default.yaml`. The data is fake, "
            "so these numbers describe the generator's rules, not real patients."
        ),
    ]
    for name, title in TITLES.items():
        columns, rows = run_query(url, name)
        parts += [
            "",
            f"## {title}",
            "",
            f"Query: [{name}]({name})",
            "",
            markdown_table(columns, rows),
        ]
    path.write_text("\n".join(parts) + "\n", encoding="utf-8", newline="")
