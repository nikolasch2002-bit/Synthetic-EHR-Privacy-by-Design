"""The prediction model's proofs (spec, "Prediction model", steps 1 to 6).

1. Leakage: every feature comes from before the index date.
2. Split by patient: no pseudonym in both sets.
4. Reproducible: the same seed gives the same coefficients.
6. Recovery: the planted effects are found. Checked on data simulated from a
   known formula (so the fitting code itself is tested), and on the full
   run's committed ml/results.json.
Also: the model never sees the test set's outcomes, and no per-patient
prediction reaches the repository.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from generator.config import load_config
from ml.cohort import FEATURES, Cohort, load_cohort, planted_log_odds
from ml.model import fit, recovery, split_by_patient
from ml.run import fit_and_evaluate

ML = Path(__file__).resolve().parent.parent / "ml"
SEED = 7


@pytest.fixture(scope="module")
def config():
    return load_config()


def simulated(config, starts: int = 20_000) -> Cohort:
    """A cohort drawn from the planted formula itself, so the right answer is known."""
    rng = np.random.default_rng(SEED)
    data = pd.DataFrame(
        {
            "egfr_per_10_below_60": np.clip(rng.normal(0.5, 1.0, starts), 0, None),
            "potassium_per_mmol_above_4_5": rng.normal(-0.1, 0.4, starts),
            "diabetes": rng.random(starts) < 0.3,
            "age_per_10_years_above_60": rng.normal(1.0, 1.2, starts),
            "combination": rng.random(starts) < 0.15,
            "loop_or_thiazide": rng.random(starts) < 0.4,
            "egfr_missing": rng.random(starts) < 0.1,
            "potassium_missing": rng.random(starts) < 0.1,
            "heart_failure": rng.random(starts) < 0.2,
            "ckd": rng.random(starts) < 0.25,
            "female": rng.random(starts) < 0.5,
        }
    ).astype(float)
    planted = planted_log_odds(config)
    intercept = config.interactions.hyperkalaemia_after_raas_start.log_odds.intercept
    logit = intercept + sum(planted[f] * data[f] for f in FEATURES)
    data["outcome"] = (rng.random(starts) < 1 / (1 + np.exp(-logit))).astype(int)
    # About 1.2 starts per patient, so the split by patient has groups to keep together.
    data["pseudonym"] = [f"SYN-P-{i // 6 * 5 + i % 5:016x}" for i in range(starts)]
    data["rule_score"] = rng.integers(0, 4, starts)
    return Cohort(data, left_out=0)


# --- Step 1: leakage ---


def test_every_feature_comes_from_before_the_index_date(built):
    cohort = load_cohort(built).data
    assert len(cohort) > 20
    for column in ("egfr_before_date", "potassium_before_date"):
        dates = cohort[column].dropna()
        index = cohort.loc[dates.index, "index_date"]
        days_before = (pd.to_datetime(index) - pd.to_datetime(dates)).dt.days
        assert days_before.between(1, 365).all(), column


# --- Step 2: split by patient ---


def test_no_patient_is_in_both_sets(config, built):
    for data in (simulated(config).data, load_cohort(built).data):
        train, test = split_by_patient(data, SEED)
        assert set(train["pseudonym"]).isdisjoint(test["pseudonym"])
        assert len(train) + len(test) == len(data)
        assert 0.25 < len(test) / len(data) < 0.35


# --- Step 4: reproducible ---


def test_the_same_seed_gives_the_same_coefficients(config):
    data = simulated(config).data
    train, _ = split_by_patient(data, SEED)
    assert fit(train, SEED).coefficients == fit(train, SEED).coefficients


def test_the_model_never_sees_the_test_outcomes(config):
    cohort = simulated(config)
    _, fitted, _, test = fit_and_evaluate(cohort, config)
    flipped = cohort.data.copy()
    flipped.loc[test.index, "outcome"] = 1 - flipped.loc[test.index, "outcome"]
    _, refitted, _, _ = fit_and_evaluate(Cohort(flipped, 0), config)
    assert refitted.coefficients == fitted.coefficients


# --- Step 6: recovery ---


def test_fitting_recovers_a_known_formula(config):
    # On data simulated from the planted formula, every coefficient comes
    # back within its 99% interval, on the features' own scale.
    train, _ = split_by_patient(simulated(config).data, SEED)
    result = recovery(fit(train, SEED), planted_log_odds(config))
    assert {f: r["within_interval"] for f, r in result.items()} == dict.fromkeys(
        FEATURES, True
    )
    assert all(r["sign_right"] for r in result.values())


def test_the_full_run_recovered_every_planted_effect():
    # ml/results.json is written by `python -m ml` from the full 40,000-patient run.
    results = json.loads((ML / "results.json").read_text(encoding="utf-8"))
    assert results["counts"]["train_events"] >= 100  # spec, "Enough data"
    for feature, r in results["recovery"]["features"].items():
        assert r["sign_right"], feature
        assert r["within_interval"], feature


def test_no_per_patient_prediction_reaches_the_repository():
    # Predictions stay in the database (ml.raas_start_prediction).
    for name in ("results.json", "RESULTS.md"):
        assert "SYN-" not in (ML / name).read_text(encoding="utf-8"), name


def test_the_prediction_table_is_in_the_data_dictionary(built):
    # Create the table as `python -m ml` does, then compare it with the dictionary.
    import psycopg

    from ml.run import PREDICTIONS_SQL
    from tests.test_database import check_dictionary

    with psycopg.connect(built) as c:
        c.execute(PREDICTIONS_SQL)
        check_dictionary(c, ("ml",))
        c.rollback()


def test_the_model_card_takes_its_numbers_from_the_results_files():
    card = (ML.parent / "governance" / "model-card.md").read_text(encoding="utf-8")
    assert "../ml/RESULTS.md" in card
    assert "../ml/results.json" in card
    # No performance number typed into the card: they live in the results files.
    for metric in ("AUROC", "Brier"):
        for line in card.splitlines():
            if metric in line:
                assert not any(ch.isdigit() for ch in line.split(metric)[1][:12]), line
