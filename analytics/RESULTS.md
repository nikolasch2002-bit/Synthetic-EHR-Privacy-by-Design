# Results

Written by `python -m analytics` from the marts: 40,000 patients, generated from the seed in `config/default.yaml`. The data is fake, so these numbers describe the generator's rules, not real patients.

## Question 1a: patients with each condition, by age band and sex (on 2016-01-01)

Query: [q1a_cohort_sizes.sql](q1a_cohort_sizes.sql)

| condition | age_band | sex | patients | with_condition | prevalence_pct |
| --- | --- | --- | --- | --- | --- |
| atrial_fibrillation | 18-29 | F | 2081 | 0 | 0.0 |
| atrial_fibrillation | 18-29 | M | 2145 | <10 | <10 |
| atrial_fibrillation | 30-39 | F | 2422 | <10 | <10 |
| atrial_fibrillation | 30-39 | M | 2305 | <10 | <10 |
| atrial_fibrillation | 40-49 | F | 2583 | <10 | <10 |
| atrial_fibrillation | 40-49 | M | 2503 | 11 | 0.4 |
| atrial_fibrillation | 50-59 | F | 3121 | 21 | 0.7 |
| atrial_fibrillation | 50-59 | M | 3192 | 57 | 1.8 |
| atrial_fibrillation | 60-69 | F | 3573 | 90 | 2.5 |
| atrial_fibrillation | 60-69 | M | 3635 | 150 | 4.1 |
| atrial_fibrillation | 70-79 | F | 3049 | 198 | 6.5 |
| atrial_fibrillation | 70-79 | M | 2989 | 319 | 10.7 |
| atrial_fibrillation | 80-89 | F | 1489 | 248 | 16.7 |
| atrial_fibrillation | 80-89 | M | 1555 | 312 | 20.1 |
| atrial_fibrillation | 90+ | F | 1698 | 372 | 21.9 |
| atrial_fibrillation | 90+ | M | 1660 | 426 | 25.7 |
| ckd | 18-29 | F | 2081 | <10 | <10 |
| ckd | 18-29 | M | 2145 | <10 | <10 |
| ckd | 30-39 | F | 2422 | 34 | 1.4 |
| ckd | 30-39 | M | 2305 | 20 | 0.9 |
| ckd | 40-49 | F | 2583 | 69 | 2.7 |
| ckd | 40-49 | M | 2503 | 68 | 2.7 |
| ckd | 50-59 | F | 3121 | 184 | 5.9 |
| ckd | 50-59 | M | 3192 | 185 | 5.8 |
| ckd | 60-69 | F | 3573 | 478 | 13.4 |
| ckd | 60-69 | M | 3635 | 456 | 12.5 |
| ckd | 70-79 | F | 3049 | 647 | 21.2 |
| ckd | 70-79 | M | 2989 | 739 | 24.7 |
| ckd | 80-89 | F | 1489 | 567 | 38.1 |
| ckd | 80-89 | M | 1555 | 571 | 36.7 |
| ckd | 90+ | F | 1698 | 715 | 42.1 |
| ckd | 90+ | M | 1660 | 642 | 38.7 |
| heart_failure | 18-29 | F | 2081 | 0 | 0.0 |
| heart_failure | 18-29 | M | 2145 | 0 | 0.0 |
| heart_failure | 30-39 | F | 2422 | 0 | 0.0 |
| heart_failure | 30-39 | M | 2305 | <10 | <10 |
| heart_failure | 40-49 | F | 2583 | <10 | <10 |
| heart_failure | 40-49 | M | 2503 | 12 | 0.5 |
| heart_failure | 50-59 | F | 3121 | 20 | 0.6 |
| heart_failure | 50-59 | M | 3192 | 34 | 1.1 |
| heart_failure | 60-69 | F | 3573 | 88 | 2.5 |
| heart_failure | 60-69 | M | 3635 | 139 | 3.8 |
| heart_failure | 70-79 | F | 3049 | 212 | 7.0 |
| heart_failure | 70-79 | M | 2989 | 332 | 11.1 |
| heart_failure | 80-89 | F | 1489 | 388 | 26.1 |
| heart_failure | 80-89 | M | 1555 | 474 | 30.5 |
| heart_failure | 90+ | F | 1698 | 762 | 44.9 |
| heart_failure | 90+ | M | 1660 | 776 | 46.7 |
| hyperlipidaemia | 18-29 | F | 2081 | 26 | 1.2 |
| hyperlipidaemia | 18-29 | M | 2145 | 47 | 2.2 |
| hyperlipidaemia | 30-39 | F | 2422 | 39 | 1.6 |
| hyperlipidaemia | 30-39 | M | 2305 | 91 | 3.9 |
| hyperlipidaemia | 40-49 | F | 2583 | 98 | 3.8 |
| hyperlipidaemia | 40-49 | M | 2503 | 160 | 6.4 |
| hyperlipidaemia | 50-59 | F | 3121 | 311 | 10.0 |
| hyperlipidaemia | 50-59 | M | 3192 | 431 | 13.5 |
| hyperlipidaemia | 60-69 | F | 3573 | 867 | 24.3 |
| hyperlipidaemia | 60-69 | M | 3635 | 891 | 24.5 |
| hyperlipidaemia | 70-79 | F | 3049 | 1025 | 33.6 |
| hyperlipidaemia | 70-79 | M | 2989 | 989 | 33.1 |
| hyperlipidaemia | 80-89 | F | 1489 | 607 | 40.8 |
| hyperlipidaemia | 80-89 | M | 1555 | 550 | 35.4 |
| hyperlipidaemia | 90+ | F | 1698 | 588 | 34.6 |
| hyperlipidaemia | 90+ | M | 1660 | 457 | 27.5 |
| hypertension | 18-29 | F | 2081 | 36 | 1.7 |
| hypertension | 18-29 | M | 2145 | 45 | 2.1 |
| hypertension | 30-39 | F | 2422 | 72 | 3.0 |
| hypertension | 30-39 | M | 2305 | 63 | 2.7 |
| hypertension | 40-49 | F | 2583 | 198 | 7.7 |
| hypertension | 40-49 | M | 2503 | 161 | 6.4 |
| hypertension | 50-59 | F | 3121 | 517 | 16.6 |
| hypertension | 50-59 | M | 3192 | 541 | 16.9 |
| hypertension | 60-69 | F | 3573 | 1128 | 31.6 |
| hypertension | 60-69 | M | 3635 | 1156 | 31.8 |
| hypertension | 70-79 | F | 3049 | 1363 | 44.7 |
| hypertension | 70-79 | M | 2989 | 1378 | 46.1 |
| hypertension | 80-89 | F | 1489 | 955 | 64.1 |
| hypertension | 80-89 | M | 1555 | 854 | 54.9 |
| hypertension | 90+ | F | 1698 | 1154 | 68.0 |
| hypertension | 90+ | M | 1660 | 946 | 57.0 |
| type2_diabetes | 18-29 | F | 2081 | 22 | 1.1 |
| type2_diabetes | 18-29 | M | 2145 | 30 | 1.4 |
| type2_diabetes | 30-39 | F | 2422 | 36 | 1.5 |
| type2_diabetes | 30-39 | M | 2305 | 44 | 1.9 |
| type2_diabetes | 40-49 | F | 2583 | 86 | 3.3 |
| type2_diabetes | 40-49 | M | 2503 | 87 | 3.5 |
| type2_diabetes | 50-59 | F | 3121 | 244 | 7.8 |
| type2_diabetes | 50-59 | M | 3192 | 311 | 9.7 |
| type2_diabetes | 60-69 | F | 3573 | 512 | 14.3 |
| type2_diabetes | 60-69 | M | 3635 | 668 | 18.4 |
| type2_diabetes | 70-79 | F | 3049 | 650 | 21.3 |
| type2_diabetes | 70-79 | M | 2989 | 827 | 27.7 |
| type2_diabetes | 80-89 | F | 1489 | 468 | 31.4 |
| type2_diabetes | 80-89 | M | 1555 | 478 | 30.7 |
| type2_diabetes | 90+ | F | 1698 | 482 | 28.4 |
| type2_diabetes | 90+ | M | 1660 | 513 | 30.9 |

## Question 1b: the 15 most common combinations of conditions (on 2016-01-01)

Query: [q1b_combinations.sql](q1b_combinations.sql)

| combination | patients | share_pct |
| --- | --- | --- |
| (none) | 22132 | 55.3 |
| hypertension | 3318 | 8.3 |
| hyperlipidaemia | 2363 | 5.9 |
| hypertension + hyperlipidaemia | 1357 | 3.4 |
| type2_diabetes | 1266 | 3.2 |
| ckd | 1070 | 2.7 |
| hypertension + ckd | 771 | 1.9 |
| hypertension + type2_diabetes | 652 | 1.6 |
| hypertension + hyperlipidaemia + type2_diabetes | 472 | 1.2 |
| hypertension + type2_diabetes + ckd | 407 | 1.0 |
| hypertension + hyperlipidaemia + ckd | 382 | 1.0 |
| hyperlipidaemia + type2_diabetes | 369 | 0.9 |
| atrial_fibrillation | 346 | 0.9 |
| hypertension + hyperlipidaemia + type2_diabetes + ckd | 325 | 0.8 |
| hypertension + heart_failure | 310 | 0.8 |

## Question 3: each drug-lab rule, found against planted

Query: [q3_drug_lab_interactions.sql](q3_drug_lab_interactions.sql)

| rule | counted_per | denominator | events | rate_pct | planted_pct | median_days_since_start |
| --- | --- | --- | --- | --- | --- | --- |
| alt_after_statin_start | start | 685 | 12 | 1.75 | 2.00 | 59 |
| hyperkalaemia_after_raas_start | formula | 3347 | 197 | 5.89 |  | 13 |
| hypokalaemia_on_diuretic | test | 56815 | 4458 | 7.85 | 8.00 | 1062 |
| inr_above_4_on_warfarin | test | 39460 | 3155 | 8.00 | 8.00 | 959 |
| metformin_with_egfr_below_30 | user | 946 | 294 | 31.08 | 30.00 | 1164 |

## Question 5 (rule baseline): hyperkalaemia after a RAAS-inhibitor start, by rule score

Query: [q5_rule_score.sql](q5_rule_score.sql)

| rule_score | starts | events | event_rate_pct |
| --- | --- | --- | --- |
| 0 | 1551 | 34 | 2.2 |
| 1 | 899 | 57 | 6.3 |
| 2 | 393 | 29 | 7.4 |
| 3 | 165 | 32 | 19.4 |
| 4 | 49 | 18 | 36.7 |
| 5 | <10 | <10 | <10 |
| not measured (left out) | 1187 |  |  |

## Question 6: HbA1c before and after metformin starts (mmol/mol)

Query: [q6_hba1c_after_metformin.sql](q6_hba1c_after_metformin.sql)

| metformin_starts | with_hba1c_before_and_after | mean_before | mean_after | mean_change | median_change |
| --- | --- | --- | --- | --- | --- |
| 1004 | 479 | 62.2 | 52.7 | -9.5 | -10.0 |

## Question 7: data quality checks (every count should be 0)

Query: [q7_data_quality.sql](q7_data_quality.sql)

| check_name | failing_rows |
| --- | --- |
| diagnoses after death | 0 |
| medicine periods starting after death | 0 |
| visits before the history starts | 0 |
| visits ending before they start | 0 |
| date keys that disagree with their timestamp | 0 |
| visits after death | 0 |
| lab tests after death | 0 |
| lab results on a visit of another patient | 0 |
| lab values outside physiological limits | 0 |
| fact rows whose patient is not in dim_patient | 0 |
