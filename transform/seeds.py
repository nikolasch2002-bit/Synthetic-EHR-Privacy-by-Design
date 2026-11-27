"""dbt seed files: the reference dimensions dim_drug, dim_lab_test and dim_diagnosis.

The config is the one source for drug classes, lab tests and the conditions'
codes; these files are written from it, and a test checks that they still
match, so the marts and the generator cannot drift apart. The names are the
project's own labels (e.g. "ramipril", "potassium"), not official ATC,
LOINC or ICD-10 titles, which wait until their terms are read (spec, "Data").
"""

import csv
import io
from pathlib import Path

from generator.config import Config
from generator.labs import STATIN_WATCH_DAYS

SEEDS = Path(__file__).resolve().parent.parent / "dbt" / "seeds"

# ICD-10 chapters by first letter, for the six conditions' codes: the chapter
# number only (its title is WHO text).
CHAPTER = {"E": "IV", "I": "IX", "N": "XIV"}


def _csv(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(["" if v is None else v for v in row] for row in rows)
    return out.getvalue()


def seed_files(config: Config) -> dict[str, str]:
    drugs = [[d.atc, name, d.drug_class] for name, d in config.drugs.items()]
    tests = [
        [
            t.loinc,
            name,
            t.unit,
            t.ref_low,
            t.ref_high,
            *t.reference("F"),
            t.limit_low,
            t.limit_high,
        ]
        for name, t in config.lab_tests.items()
    ]
    diagnoses = [
        [c.icd10, name, CHAPTER[c.icd10[0]]] for name, c in config.conditions.items()
    ]
    return {
        "dim_drug.csv": _csv(["atc_code", "drug_name", "drug_class"], drugs),
        "dim_lab_test.csv": _csv(
            [
                "loinc_code",
                "test_name",
                "unit",
                "male_reference_low",
                "male_reference_high",
                "female_reference_low",
                "female_reference_high",
                "limit_low",
                "limit_high",
            ],
            tests,
        ),
        "dim_diagnosis.csv": _csv(
            ["icd10_code", "condition", "icd10_chapter"], diagnoses
        ),
        "dim_drug_lab_rule.csv": _csv(
            [
                "rule",
                "drug_class",
                "test_name",
                "comparison",
                "threshold",
                "threshold_times_upper_limit",
                "window_days_after_start",
                "planted_rate",
                "planted_per",
            ],
            drug_lab_rules(config),
        ),
    }


def drug_lab_rules(config: Config) -> list[list]:
    """The five interactions (docs/clinical-rules.md, section 11): one row per
    rule and medicine class. A window means the rule is about a start: only
    tests that many days after the start count. planted_rate is what the
    generator planted, for the planted-rate tests; the hyperkalaemia rule has
    a formula instead of one rate."""
    i = config.interactions
    hk, low, inr, alt = (
        i.hyperkalaemia_after_raas_start,
        i.hypokalaemia_on_diuretic,
        i.inr_above_4_on_warfarin,
        i.alt_after_statin_start,
    )
    keep_metformin = round(1 - config.medication_rules.metformin_stop_below_egfr_30, 4)
    rows = []
    for drug_class in ("ace_inhibitor", "arb", "mra"):
        rows.append(["hyperkalaemia_after_raas_start", drug_class, "potassium", ">=",
                     hk.threshold, False, hk.window_days, None, "formula"])  # fmt: skip
    for drug_class in ("loop_diuretic", "thiazide"):
        rows.append(["hypokalaemia_on_diuretic", drug_class, "potassium", "<",
                     low.threshold, False, None, low.chance_per_test, "test"])  # fmt: skip
    rows.append(["inr_above_4_on_warfarin", "vka", "inr", ">",
                 inr.threshold, False, None, inr.chance_per_test, "test"])  # fmt: skip
    rows.append(["metformin_with_egfr_below_30", "biguanide", "egfr", "<",
                 30, False, None, keep_metformin, "user"])  # fmt: skip
    rows.append(["alt_after_statin_start", "statin", "alt", ">",
                 alt.times_uln, True, STATIN_WATCH_DAYS, alt.chance, "start"])  # fmt: skip
    return rows


def write_seeds(config: Config, directory: Path = SEEDS) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in seed_files(config).items():
        (directory / name).write_text(text, encoding="utf-8", newline="")
