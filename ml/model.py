"""Steps 2 to 6: split by patient, the rule baseline, the model, evaluation, recovery.

The logistic regression is fitted without a penalty: a penalty shrinks the
coefficients towards 0, which would bias the comparison with the planted
log-odds. Features are standardized for the fit (spec), and the coefficients
are converted back to the features' own scale for reading and comparing.
"""

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler

from ml.cohort import FEATURES

TEST_SHARE = 0.30
RECOVERY_CONFIDENCE = 0.99  # the stated tolerance: within the 99% confidence interval


def split_by_patient(
    data: pd.DataFrame, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """70/30 by patient: a patient with several starts stays on one side."""
    splitter = GroupShuffleSplit(n_splits=1, test_size=TEST_SHARE, random_state=seed)
    train_index, test_index = next(splitter.split(data, groups=data["pseudonym"]))
    return data.iloc[train_index], data.iloc[test_index]


@dataclass
class FittedModel:
    intercept: float  # on the features' own scale
    coefficients: dict[str, float]  # log-odds per unit of each feature
    standard_errors: dict[str, float]
    scaler: StandardScaler
    model: LogisticRegression

    def predict(self, data: pd.DataFrame) -> np.ndarray:
        x = data[FEATURES].to_numpy(float)
        return self.model.predict_proba(self.scaler.transform(x))[:, 1]


def fit(train: pd.DataFrame, seed: int) -> FittedModel:
    """Logistic regression on the training set only."""
    x, y = train[FEATURES].to_numpy(float), train["outcome"].to_numpy(int)
    scaler = StandardScaler().fit(x)
    # C is the inverse of the penalty's strength: infinite C means no penalty.
    model = LogisticRegression(C=np.inf, max_iter=10_000, random_state=seed)
    model.fit(scaler.transform(x), y)
    # Back to the features' own scale: beta = beta_std / sd, and the intercept
    # absorbs the centring.
    beta = model.coef_[0] / scaler.scale_
    intercept = float(
        model.intercept_[0] - np.sum(model.coef_[0] * scaler.mean_ / scaler.scale_)
    )
    # Standard errors from the inverse of the Fisher information, X' W X.
    design = np.column_stack([np.ones(len(x)), x])
    p = 1 / (1 + np.exp(-(design @ np.concatenate([[intercept], beta]))))
    information = design.T @ (design * (p * (1 - p))[:, None])
    errors = np.sqrt(np.diag(np.linalg.inv(information)))[1:]
    return FittedModel(
        intercept,
        dict(zip(FEATURES, beta.tolist(), strict=True)),
        dict(zip(FEATURES, errors.tolist(), strict=True)),
        scaler,
        model,
    )


def baseline_probabilities(train: pd.DataFrame, data: pd.DataFrame) -> np.ndarray:
    """The rule score as a probability: the training set's event rate at each
    score. A score not seen in training gets the overall training rate."""
    rate = train.groupby("rule_score")["outcome"].mean()
    overall = train["outcome"].mean()
    return data["rule_score"].map(rate).fillna(overall).to_numpy(float)


def evaluate(y: np.ndarray, probability: np.ndarray) -> dict:
    """AUROC (ranking), Brier score (accuracy of the probabilities), and a
    calibration curve: predicted against observed, in five equal-sized groups."""
    observed, predicted = calibration_curve(
        y, probability, n_bins=5, strategy="quantile"
    )
    return {
        "auroc": float(roc_auc_score(y, probability)),
        "brier": float(brier_score_loss(y, probability)),
        "calibration": {
            "predicted": [float(v) for v in predicted],
            "observed": [float(v) for v in observed],
        },
    }


def recovery(fitted: FittedModel, planted: dict[str, float]) -> dict[str, dict]:
    """Step 6: for each feature, the fitted and planted odds ratios, and whether
    the planted value lies within the fitted coefficient's confidence interval
    (and, for a planted effect, whether the sign is right)."""
    z = NormalDist().inv_cdf(0.5 + RECOVERY_CONFIDENCE / 2)
    result = {}
    for feature in FEATURES:
        beta, se, truth = (
            fitted.coefficients[feature],
            fitted.standard_errors[feature],
            planted[feature],
        )
        low, high = beta - z * se, beta + z * se
        result[feature] = {
            "planted_log_odds": truth,
            "fitted_log_odds": beta,
            "standard_error": se,
            "planted_odds_ratio": float(np.exp(truth)),
            "fitted_odds_ratio": float(np.exp(beta)),
            "odds_ratio_interval": [float(np.exp(low)), float(np.exp(high))],
            "sign_right": bool(truth == 0 or np.sign(beta) == np.sign(truth)),
            "within_interval": bool(low <= truth <= high),
        }
    return result
