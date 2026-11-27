"""Step 1: the cohort and its features, from marts.fact_raas_start.

One row per RAAS-inhibitor start with potassium measured on days 1-30 after
the index date; starts without are left out and counted (not measured is not
the same as normal). Every feature comes from before the index date: the
mart's dbt test checks the dates, and so does tests/test_ml.py.

Features are put on the same scale as the generator's planted formula
(docs/clinical-rules.md, section 11), so the fitted coefficients can be
compared with the planted log-odds directly.
"""

from dataclasses import dataclass

import pandas as pd
import psycopg

from generator.config import Config

# Feature -> the planted log-odds it should recover (None: planted at 0).
PLANTED_NAME = {
    "egfr_per_10_below_60": "egfr_per_10_below_60",
    "potassium_per_mmol_above_4_5": "potassium_per_mmol_above_4_5",
    "diabetes": "diabetes",
    "age_per_10_years_above_60": "age_per_10_years_above_60",
    "combination": "combination",
    "loop_or_thiazide": "loop_or_thiazide",
    # In the model, but planted with no effect: the model should find about 0.
    "egfr_missing": None,
    "potassium_missing": None,
    "heart_failure": None,
    "ckd": None,
    "female": None,
}
FEATURES = list(PLANTED_NAME)

QUERY = """
select
    pseudonym, drug_class, index_date, sex, age,
    egfr_before, egfr_before_date, potassium_before, potassium_before_date,
    egfr_missing, potassium_missing, diabetes, heart_failure, ckd,
    combination, loop_or_thiazide, rule_score, potassium_measured, hyperkalaemia
from marts.fact_raas_start
order by raas_start_key
"""


@dataclass
class Cohort:
    data: pd.DataFrame  # one row per measured start: features, outcome, keys
    left_out: int  # starts with no potassium measured in the window


def planted_log_odds(config: Config) -> dict[str, float]:
    """Each feature's true log-odds, as the generator planted it."""
    c = config.interactions.hyperkalaemia_after_raas_start.log_odds
    return {f: (getattr(c, name) if name else 0.0) for f, name in PLANTED_NAME.items()}


def features(rows: pd.DataFrame) -> pd.DataFrame:
    """The model's features. A missing result gets its "missing" flag, and the
    value at which the planted formula adds nothing (eGFR 60 or above,
    potassium 4.5), so the flag carries what the missing value hides."""
    egfr = rows["egfr_before"].astype(float)
    potassium = rows["potassium_before"].astype(float)
    return pd.DataFrame(
        {
            "egfr_per_10_below_60": ((60 - egfr).clip(lower=0) / 10).fillna(0.0),
            "potassium_per_mmol_above_4_5": (potassium - 4.5).fillna(0.0),
            "diabetes": rows["diabetes"].astype(float),
            "age_per_10_years_above_60": (rows["age"].astype(float) - 60) / 10,
            "combination": rows["combination"].astype(float),
            "loop_or_thiazide": rows["loop_or_thiazide"].astype(float),
            "egfr_missing": rows["egfr_missing"].astype(float),
            "potassium_missing": rows["potassium_missing"].astype(float),
            "heart_failure": rows["heart_failure"].astype(float),
            "ckd": rows["ckd"].astype(float),
            "female": (rows["sex"] == "F").astype(float),
        },
        index=rows.index,
    )[FEATURES]


def load_cohort(url: str) -> Cohort:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(QUERY)
        rows = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
    measured = rows[rows["potassium_measured"]].reset_index(drop=True)
    data = pd.concat(
        [
            measured[["pseudonym", "drug_class", "index_date", "rule_score"]],
            measured[["egfr_before_date", "potassium_before_date"]],
            features(measured),
            measured["hyperkalaemia"].astype(int).rename("outcome"),
        ],
        axis=1,
    )
    return Cohort(data, left_out=int((~rows["potassium_measured"]).sum()))
