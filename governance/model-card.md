# Model card: hyperkalaemia after a RAAS-inhibitor start

> **Draft by the assistant, 2026-11-27. The owner rewrites it before it counts** (the regulatory section is a legal note). Every number about the model's performance is in [ml/RESULTS.md](../ml/RESULTS.md) and [ml/results.json](../ml/results.json), written by the evaluation run (`python -m ml`); this card repeats none of them, so it cannot drift from them.

## What it is

A **statistical model**: one logistic regression (scikit-learn), predicting the chance of hyperkalaemia (a potassium of 5.5 mmol/L or more) in the 30 days after a patient starts an ACE inhibitor, an ARB or spironolactone. It is compared with a simple rule score, which was written by hand.

## Intended use

**Learning and demonstration only.** It shows the machine-learning workflow on data with a known answer: a cohort with no leakage, a split by patient, a baseline, evaluation on held-out data, and a check against the truth. It is **not for clinical use**, and must not inform any decision about a real patient.

## Training data, and the one thing to know about it

- The data is **entirely synthetic**, made by this project's generator from a seed ([docs/clinical-rules.md](../docs/clinical-rules.md)). No real person's data was used at any stage.
- The outcome was **planted** by a logistic formula whose coefficients are in the config (clinical-rules.md, section 11). So **the model learns the generator, not medicine.** Its coefficients describe the rules this project wrote. They say nothing about real patients, and the scores have no meaning outside this dataset.
- That is also what makes step 6 possible: on real data the true effects are unknown, and here they are not.

**Cohort:** every RAAS-inhibitor start from 2017-01-01 (an order with no order of the same class in the 180 days before), from `marts.fact_raas_start`. Starts with no potassium measured in the 30 days after are **left out and counted**, because not measured is not the same as normal. The counts are in ml/RESULTS.md.

## Features

Known before the index date only (a dbt test and a pytest check the dates):

| Feature | Meaning |
| --- | --- |
| `egfr_per_10_below_60` | How far the most recent eGFR in the 365 days before is below 60, per 10 |
| `potassium_per_mmol_above_4_5` | The most recent potassium in the 365 days before, minus 4.5 |
| `egfr_missing`, `potassium_missing` | No such result in the 365 days (the value is then set where the formula adds nothing) |
| `diabetes`, `heart_failure`, `ckd` | On the problem list by the index date |
| `age_per_10_years_above_60` | Age reached in the index year, minus 60, per 10 years |
| `combination` | An ACE inhibitor or ARB together with spironolactone on the index date |
| `loop_or_thiazide` | A loop or thiazide diuretic on the index date |
| `female` | Sex |

Features are put on the planted formula's scale, so each coefficient can be compared with its planted value. `heart_failure`, `ckd`, `female` and the missing flags were planted with no effect, so the model should find none.

## Method

1. **Split by patient**, 70/30, with the config's seed: a patient with several starts is on one side only.
2. **Rule baseline:** one point each for eGFR < 45, potassium > 5.0, the combination, diabetes, age ≥ 75. It is invented for this project, not a published score. As a probability: the training set's event rate at each score.
3. **Model:** logistic regression on standardized features, **without a penalty** (a penalty would shrink the coefficients and bias the comparison with the truth). Fitted on the training set only; a test shows that flipping every test-set outcome changes nothing in the fit.
4. **Evaluation on the test set only:** AUROC (ranking), Brier score (accuracy of the probabilities) and a calibration plot ([ml/calibration.png](../ml/calibration.png)), for the model and the baseline.
5. **Check against the truth:** for each feature, the planted log-odds should lie within the fitted coefficient's **99% confidence interval**, and a planted effect should have the right sign.

## Limits

- It learns the generator. Clinical realism is limited to what the rules encode.
- Few events in training, just above the spec's minimum of 100 (the count is in ml/RESULTS.md): wide intervals, and a small test set.
- The planted formula used exact age and, for a missing result, the true level; the model sees the birth-year age and a missing flag. These differ slightly, on purpose: the model sees what an analyst would.
- Where two starts' 30-day windows overlap, the earlier start's outcome decides both.
- Calibration was not adjusted; the plot shows how far it is off.

## Privacy

The model is trained on pseudonymized marts. Predictions are per start, so they stay in the database (`ml.raas_start_prediction`), never in the repository; a test checks that no pseudonym is in the results files. Only aggregates are published.

## Regulatory position (draft legal note; to verify)

*Not legal advice. Read from a third-party mirror of the published text ([artificialintelligenceact.eu](https://artificialintelligenceact.eu/article/3/)), because EUR-Lex did not load; the mirror may show later amendments. Check the wording against [EUR-Lex](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng) before relying on it.*

- **Is it an "AI system"?** Probably yes. The EU AI Act (Regulation (EU) 2024/1689), Art. 3(1), defines an AI system as a machine-based system that infers, from its input, how to generate outputs such as predictions. Recital 12 names machine-learning approaches that learn from data as techniques that enable inference. A logistic regression fitted to data learns its mapping from data. The **rule score is probably not** an AI system: Recital 12 excludes systems based on rules defined solely by natural persons.
- **Does the Act apply here?** Probably not, in this form. Art. 2(8) excludes research, testing and development before an AI system is placed on the market or put into service, and Art. 2(6) excludes systems developed and put into service for the sole purpose of scientific research and development. This model is neither placed on the market nor put into service.
- **If it were used in care:** none of the Annex III areas names a clinical prediction like this one. The likely route to "high-risk" would be Art. 6(1) with Annex I, Section A, points 11 and 12: the Medical Device Regulation (EU) 2017/745 or the In Vitro Diagnostic Regulation (EU) 2017/746, if the software were a medical device needing third-party conformity assessment. Whether it would be is decided under those Regulations, which have not been read for this note.
