"""Run the six steps and write the results: `python -m ml`.

Writes ml/results.json (every number, for the model card and the tests),
ml/RESULTS.md (the same, readable), ml/calibration.png, and the predictions
to `ml.raas_start_prediction` in the database. Predictions are per start, so
they stay in the database, never in the repository (spec, "Prediction model",
"Privacy").
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to a file; no window
import matplotlib.pyplot as plt
import psycopg

from generator.config import Config
from ml.cohort import FEATURES, Cohort, load_cohort, planted_log_odds
from ml.model import (
    RECOVERY_CONFIDENCE,
    TEST_SHARE,
    baseline_probabilities,
    evaluate,
    fit,
    recovery,
    split_by_patient,
)

HERE = Path(__file__).resolve().parent
MIN_TRAINING_EVENTS = 100  # about 10 events per feature (spec, "Enough data")

PREDICTIONS_SQL = """
create schema if not exists ml;
drop table if exists ml.raas_start_prediction;
create table ml.raas_start_prediction (
    pseudonym text not null,
    drug_class text not null,
    index_date date not null,
    split text not null check (split in ('train', 'test')),
    model_probability numeric not null,
    baseline_probability numeric not null,
    primary key (pseudonym, drug_class, index_date)
);
-- Pseudonymous, per start: the same readers as the marts.
grant usage on schema ml to researcher, data_steward, etl;
grant select on ml.raas_start_prediction to researcher, data_steward;
grant select, insert, update, delete on ml.raas_start_prediction to etl;
"""


def rounded(value, digits: int = 4):
    """Round every float, so results.json does not change with the last digit."""
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {k: rounded(v, digits) for k, v in value.items()}
    if isinstance(value, list):
        return [rounded(v, digits) for v in value]
    return value


def run(
    url: str, config: Config, out_dir: Path = HERE, write_predictions: bool = True
) -> dict:
    """Load the cohort, fit and evaluate, write the results (and predictions)."""
    cohort = load_cohort(url)
    results, fitted, train, test = fit_and_evaluate(cohort, config)
    (out_dir / "results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )
    write_markdown(results, out_dir / "RESULTS.md")
    plot_calibration(results, out_dir / "calibration.png")
    if write_predictions:
        save_predictions(url, fitted, cohort.data, train, test, baseline_probabilities)
    return results


def fit_and_evaluate(
    cohort: Cohort, config: Config, min_events: int = MIN_TRAINING_EVENTS
):
    """Steps 2 to 6 on a cohort, without the database. The model is fitted on
    the training set only; the test set is used only to evaluate."""
    train, test = split_by_patient(cohort.data, config.seed)
    if train["outcome"].sum() < min_events:
        raise RuntimeError(
            f"only {train['outcome'].sum()} events in training; the spec needs {min_events}"
        )
    fitted = fit(train, config.seed)
    model_test = fitted.predict(test)
    baseline_test = baseline_probabilities(train, test)
    y_test = test["outcome"].to_numpy(int)

    results = rounded(
        {
            "seed": config.seed,
            "counts": {
                "starts_measured": len(cohort.data),
                "starts_left_out_not_measured": cohort.left_out,
                "patients": int(cohort.data["pseudonym"].nunique()),
                "train_starts": len(train),
                "train_events": int(train["outcome"].sum()),
                "test_starts": len(test),
                "test_events": int(y_test.sum()),
            },
            "split": {"by": "patient", "test_share": TEST_SHARE},
            "model": {
                "intercept": fitted.intercept,
                "coefficients": fitted.coefficients,
            },
            "test_set": {
                "model": evaluate(y_test, model_test),
                "baseline": evaluate(y_test, baseline_test),
            },
            "recovery": {
                "confidence": RECOVERY_CONFIDENCE,
                "features": recovery(fitted, planted_log_odds(config)),
            },
        }
    )
    return results, fitted, train, test


def save_predictions(url, fitted, data, train, test, baseline) -> None:
    split = data.index.isin(test.index)
    rows = zip(
        data["pseudonym"], data["drug_class"], data["index_date"],
        ["test" if s else "train" for s in split],
        fitted.predict(data), baseline(train, data), strict=True,
    )  # fmt: skip
    with psycopg.connect(url) as conn:
        conn.execute(PREDICTIONS_SQL)
        with (
            conn.cursor() as cur,
            cur.copy("copy ml.raas_start_prediction from stdin") as copy,
        ):
            for row in rows:
                copy.write_row(row)


def write_markdown(results: dict, path: Path) -> None:
    c, t, r = results["counts"], results["test_set"], results["recovery"]
    lines = [
        "# Prediction model: results",
        "",
        (
            "Written by `python -m ml` from the full generated dataset. A statistical model of "
            "the generator's own data: **it learns the generator, not medicine**, and says "
            "nothing about real patients."
        ),
        "",
        "## Data",
        "",
        "| | Starts | Events (K⁺ ≥ 5.5 in 30 days) |",
        "| --- | ---: | ---: |",
        f"| Training (70%, by patient) | {c['train_starts']} | {c['train_events']} |",
        f"| Test (30%) | {c['test_starts']} | {c['test_events']} |",
        f"| Left out: potassium not measured | {c['starts_left_out_not_measured']} | |",
        "",
        "## Test set: model against the rule baseline",
        "",
        "| | AUROC | Brier score |",
        "| --- | ---: | ---: |",
        f"| Logistic regression | {t['model']['auroc']} | {t['model']['brier']} |",
        f"| Rule score (baseline) | {t['baseline']['auroc']} | {t['baseline']['brier']} |",
        "",
        (
            "AUROC: how well the scores rank starts with an event above those without "
            "(0.5 is chance). Brier score: the mean squared error of the probabilities "
            "(lower is better). Calibration: [calibration.png](calibration.png)."
        ),
        "",
        f"## Check against the truth (planted value within the {int(r['confidence'] * 100)}% interval)",
        "",
        "| Feature | Planted OR | Fitted OR | Interval | Sign right | Within |",
        "| --- | ---: | ---: | --- | --- | --- |",
    ]
    for feature in FEATURES:
        f = r["features"][feature]
        low, high = f["odds_ratio_interval"]
        lines.append(
            f"| {feature} | {f['planted_odds_ratio']} | {f['fitted_odds_ratio']} | "
            f"{low}–{high} | {'yes' if f['sign_right'] else 'no'} | "
            f"{'yes' if f['within_interval'] else 'no'} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def plot_calibration(results: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", label="perfect")
    for name, label in (("model", "logistic regression"), ("baseline", "rule score")):
        cal = results["test_set"][name]["calibration"]
        ax.plot(cal["predicted"], cal["observed"], marker="o", label=label)
    top = max(
        max(results["test_set"][n]["calibration"][k]) for n in ("model", "baseline")
        for k in ("predicted", "observed")
    ) * 1.1  # fmt: skip
    ax.set(
        xlim=(0, top), ylim=(0, top), xlabel="Predicted chance", ylabel="Observed share"
    )
    ax.set_title("Calibration on the test set (five equal groups)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(
        path, dpi=120, metadata={"Software": None}
    )  # no version stamp: stable bytes
    plt.close(fig)


def main() -> None:
    from generator.config import load_config
    from loader.load import database_url

    results = run(database_url(), load_config())
    print(json.dumps(results["counts"], indent=2))
    print(
        "test AUROC: model",
        results["test_set"]["model"]["auroc"],
        "baseline",
        results["test_set"]["baseline"]["auroc"],
    )
