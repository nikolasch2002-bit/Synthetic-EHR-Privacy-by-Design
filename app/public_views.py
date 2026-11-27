"""Pages anyone may see: suppressed aggregates from marts_public, and the
model's evaluation (aggregate numbers from ml/results.json)."""

import json
from pathlib import Path

import streamlit as st

from app.db import PUBLIC_ROLE, Refused, query

RESULTS = Path(__file__).resolve().parent.parent / "ml" / "results.json"
FAKE_DATA_NOTE = (
    "Every row behind these numbers is fake, generated from a seed by this project's own "
    "clinical rules, and protected as if it were real. Nothing here is clinical advice."
)
SUPPRESSED_NOTE = "Counts below 10 are hidden (shown empty), and no totals are given, so a hidden count cannot be worked out."


def show_refused(error: Refused, role: str) -> None:
    st.warning(f"The database refused this for the role `{role}`: {error}")


def conditions_page(role: str = PUBLIC_ROLE) -> None:
    st.header("Conditions by age and sex")
    st.caption(FAKE_DATA_NOTE)
    try:
        data = query(
            role,
            "select condition, age_band, sex, patients from marts_public.public_condition_count "
            "order by condition, age_band, sex",
        )
    except Refused as error:
        return show_refused(error, role)
    condition = st.selectbox("Condition", sorted(data["condition"].unique()))
    table = data[data["condition"] == condition].pivot(
        index="age_band", columns="sex", values="patients"
    )
    st.dataframe(table, width="stretch")
    st.caption("Patients with the condition on 2016-01-01. " + SUPPRESSED_NOTE)


def interactions_page(role: str = PUBLIC_ROLE) -> None:
    st.header("Drug–lab interactions")
    st.caption(FAKE_DATA_NOTE)
    try:
        data = query(
            role,
            "select rule, results, events, rate_pct from marts_public.public_interaction_rate order by rule",
        )
    except Refused as error:
        return show_refused(error, role)
    st.dataframe(data, width="stretch", hide_index=True)
    st.caption(
        "Lab results taken while on a medicine linked to that test, how many broke the rule, "
        "and the rate. The generator planted these rates, so the analysis has a known right answer. "
        + SUPPRESSED_NOTE
    )


def model_page(role: str = PUBLIC_ROLE) -> None:
    st.header("Predicting hyperkalaemia after a RAAS-inhibitor start")
    st.info(
        "A statistical model of this project's own fake data. **It learns the generator, not "
        "medicine**: its scores say nothing about real patients and must not be used in care."
    )
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    model, baseline = results["test_set"]["model"], results["test_set"]["baseline"]
    left, right = st.columns(2)
    left.metric("AUROC, logistic regression", model["auroc"])
    right.metric("AUROC, rule score", baseline["auroc"])
    left.metric("Brier score, logistic regression", model["brier"])
    right.metric("Brier score, rule score", baseline["brier"])
    st.subheader("Did the model find what the generator planted?")
    rows = [
        {
            "feature": feature,
            "planted odds ratio": r["planted_odds_ratio"],
            "fitted odds ratio": r["fitted_odds_ratio"],
            "planted value within the 99% interval": "yes"
            if r["within_interval"]
            else "no",
        }
        for feature, r in results["recovery"]["features"].items()
    ]
    st.dataframe(rows, width="stretch", hide_index=True)
    st.subheader("Hyperkalaemia by rule score")
    try:
        scores = query(
            role,
            "select rule_score, starts, events, event_rate_pct from marts_public.public_rule_score order by rule_score",
        )
    except Refused as error:
        return show_refused(error, role)
    st.dataframe(scores, width="stretch", hide_index=True)
    st.caption(
        "The rule score is invented for this project: one point each for eGFR below 45, potassium "
        "above 5.0, an ACE inhibitor or ARB with spironolactone, diabetes, and age 75 or over. "
        + SUPPRESSED_NOTE
    )


PAGES = {
    "Conditions": conditions_page,
    "Drug–lab interactions": interactions_page,
    "Prediction model": model_page,
}
