# Prediction model: results

Written by `python -m ml` from the full generated dataset. A statistical model of the generator's own data: **it learns the generator, not medicine**, and says nothing about real patients.

## Data

| | Starts | Events (K⁺ ≥ 5.5 in 30 days) |
| --- | ---: | ---: |
| Training (70%, by patient) | 2144 | 131 |
| Test (30%) | 920 | 44 |
| Left out: potassium not measured | 1187 | |

## Test set: model against the rule baseline

| | AUROC | Brier score |
| --- | ---: | ---: |
| Logistic regression | 0.7662 | 0.0397 |
| Rule score (baseline) | 0.7351 | 0.0431 |

AUROC: how well the scores rank starts with an event above those without (0.5 is chance). Brier score: the mean squared error of the probabilities (lower is better). Calibration: [calibration.png](calibration.png).

## Check against the truth (planted value within the 99% interval)

| Feature | Planted OR | Fitted OR | Interval | Sign right | Within |
| --- | ---: | ---: | --- | --- | --- |
| egfr_per_10_below_60 | 1.3499 | 1.3456 | 1.0529–1.7197 | yes | yes |
| potassium_per_mmol_above_4_5 | 3.3201 | 3.8837 | 1.9098–7.8977 | yes | yes |
| diabetes | 1.6487 | 2.2403 | 1.2782–3.9267 | yes | yes |
| age_per_10_years_above_60 | 1.284 | 1.3402 | 1.0475–1.7146 | yes | yes |
| combination | 2.7183 | 2.3922 | 1.0035–5.7029 | yes | yes |
| loop_or_thiazide | 0.4966 | 0.4454 | 0.2284–0.8686 | yes | yes |
| egfr_missing | 1.0 | 1.3811 | 0.4603–4.1437 | yes | yes |
| potassium_missing | 1.0 | 0.7312 | 0.2407–2.2209 | yes | yes |
| heart_failure | 1.0 | 1.0457 | 0.4566–2.3953 | yes | yes |
| ckd | 1.0 | 0.6713 | 0.2959–1.5229 | yes | yes |
| female | 1.0 | 1.1964 | 0.7239–1.9772 | yes | yes |
