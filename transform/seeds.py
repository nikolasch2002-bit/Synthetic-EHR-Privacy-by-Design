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
    }


def write_seeds(config: Config, directory: Path = SEEDS) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in seed_files(config).items():
        (directory / name).write_text(text, encoding="utf-8", newline="")
