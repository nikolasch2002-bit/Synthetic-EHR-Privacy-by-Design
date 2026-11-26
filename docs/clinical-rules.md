# Clinical rules and the rates behind them

> **Approved by the owner, 2026-11-26, as drafted by the assistant.** These numbers go into `config/default.yaml`; a change to one is made here first, with its reason. Each number is marked:
> **sourced**: taken from the named table, retrieved 2026-11-26;
> **derived**: calculated from sourced numbers, the calculation stated;
> **assumed**: a judgement with no source yet, *to verify*.

The generator makes a closed cohort of adult hospital patients (spec, "Clinical content"): everyone is 18 or older and alive on 2016-01-01, and is followed until death or 2025-12-31.

## 1. Age and sex mix on 2016-01-01

| Age band | Share | Status |
| --- | ---: | --- |
| 18–29 | 11.6% | derived |
| 30–39 | 11.9% | derived |
| 40–49 | 12.8% | derived |
| 50–54 | 7.7% | derived |
| 55–64 | 16.7% | derived |
| 65–74 | 20.1% | derived |
| 75+ | 19.2% | derived |

**How:** the Dutch adult population on 1 January 2016, by age (CBS [03759ned](https://opendata.cbs.nl/statline/#/CBS/nl/dataset/03759ned/table)), weighted by the share of each age band admitted to hospital in the past 12 months in 2024 (CBS [85454NED](https://opendata.cbs.nl/statline/#/CBS/nl/dataset/85454NED/table), "Opname met overnachtingen": 4.2% at 20–30 up to 13.5% at 75+). So older people are as over-represented as they are among people admitted to hospital.

*Alternative:* weight by "at least one contact with a specialist" instead (34% to 60% by age, same table). That gives a younger mix (31% aged 65+, against 39% here).

**Sex:** 50% women, 50% men (*assumed*; to be replaced with the same population-and-admissions calculation by sex if the owner wants it).

## 2. Prevalence of the six conditions by age and sex

Persons known to their GP with each diagnosis, **per 1,000**, 2024 (final figures), from CBS [86055NED](https://opendata.cbs.nl/statline/#/CBS/nl/dataset/86055NED/table), "Personen naar bij de huisarts bekende diagnose; leeftijd, geslacht". **Sourced.** The CBS reports ICPC codes (the GP's coding system); the ICD-10 code each one maps to is in the first column.

| Condition (ICD-10 ← ICPC) | Sex | 20–44 | 45–49 | 50–54 | 55–59 | 60–64 | 65–69 | 70–74 | 75–79 | 80–84 | 85–89 | 90+ |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hypertension (I10 ← K86–K87) | M | 18 | 81 | 137 | 208 | 288 | 374 | 450 | 510 | 553 | 561 | 570 |
| | F | 22 | 85 | 143 | 208 | 282 | 366 | 450 | 542 | 615 | 666 | 668 |
| Diabetes, all types (← T90) | M | 13 | 44 | 73 | 101 | 137 | 172 | 214 | 242 | 265 | 253 | 224 |
| | F | 13 | 34 | 53 | 75 | 100 | 128 | 155 | 188 | 220 | 229 | 203 |
| Hyperlipidaemia (E78 ← T93) | M | 19 | 73 | 110 | 146 | 188 | 227 | 259 | 267 | 260 | 237 | 195 |
| | F | 13 | 43 | 73 | 120 | 175 | 234 | 277 | 308 | 309 | 297 | 237 |
| Atrial fibrillation (I48 ← K78) | M | 1 | 5 | 10 | 18 | 32 | 55 | 85 | 124 | 166 | 189 | 213 |
| | F | 0 | 2 | 4 | 9 | 17 | 30 | 51 | 85 | 128 | 151 | 175 |
| Heart failure (I50 ← K77) | M | 1 | 3 | 6 | 9 | 14 | 23 | 39 | 64 | 102 | 163 | 240 |
| | F | 0 | 2 | 4 | 6 | 9 | 16 | 28 | 48 | 83 | 138 | 220 |

**Type 2 diabetes (E11):** T90 counts all types. Of people with diabetes known to their GP in 2022, about 91% had type 2 (1,064,800 of 1,172,900; [Nivel 2022](https://nivel.nl/en/publicatie/diabetes-mellitus-type-1-en-type-2-nederland-prevalentie-en-incidentie-2022)). So E11 = 0.91 × the T90 row. **Derived.** *To verify:* the share of type 1 is higher at young ages, so a single 0.91 overstates type 2 under 45.

**Chronic kidney disease (N18):** the CBS table has no CKD row. The Nierstichting gives about 10% of the Dutch population, rising to over 40% above 70, counting albuminuria as well as eGFR < 60 ([Nierstichting factsheet](https://tools.nierstichting.nl/documents/399/FS1-Nierennierschade_en_nierfalen.22.pdf)). Most of those are not diagnosed. Proposed **recorded** CKD (stage 3–5, eGFR < 60), *assumed*:

| | 18–44 | 45–64 | 65–74 | 75+ |
| --- | ---: | ---: | ---: | ---: |
| CKD per 1,000 | 5 | 40 | 120 | 250 |

**These are GP (general population) rates, used for hospital patients.** Hospital patients are sicker than people of the same age outside hospital, so the real rates are higher. Section 3 raises them through co-occurrence; there is no separate "hospital factor", because no source gives one.

## 3. Co-occurrence

Conditions are drawn in a fixed order: hypertension, hyperlipidaemia, diabetes, CKD, atrial fibrillation, heart failure. Each one's chance starts from section 2's rate for the patient's age and sex, and is raised by the conditions already drawn, as an odds ratio. All odds ratios *assumed*, to verify against literature:

| Condition | Raised by (odds ratio) |
| --- | --- |
| Hyperlipidaemia | hypertension 2.0 |
| Type 2 diabetes | hypertension 2.0, hyperlipidaemia 1.5 |
| CKD | diabetes 2.5, hypertension 2.0 |
| Atrial fibrillation | hypertension 1.5 |
| Heart failure | atrial fibrillation 4.0, hypertension 2.0, diabetes 1.8, CKD 2.0 |

This makes each prevalence end up somewhat above the GP rate in section 2, which fits a hospital population. The prevalence test then checks the output against the expected rate calculated from these same numbers, not against section 2 directly.

## 4. Onset during follow-up

People who have a condition on 2016-01-01 get an onset date before 2016: 1 to 15 years earlier, uniform (*assumed*). New cases during 2016–2025 come from the rise in prevalence with age: the yearly chance of a new diagnosis at age *a* is the prevalence increase from *a* to *a*+1, divided by the share still free of the condition (**derived** from section 2; it ignores the extra deaths among people with the condition, so it slightly underestimates incidence).

## 5. Mortality

The yearly chance of dying by age and sex comes from the CBS life table for 2019, chosen as a recent year before COVID-19 (CBS [37360ned](https://opendata.cbs.nl/statline/#/CBS/nl/dataset/37360ned/table), "Sterftekans"). **Sourced.** Examples:

| Age | 50 | 60 | 65 | 70 | 75 | 80 | 85 | 90 | 95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Men | 0.23% | 0.63% | 1.01% | 1.67% | 2.88% | 5.16% | 9.36% | 17.1% | 27.8% |
| Women | 0.16% | 0.46% | 0.72% | 1.22% | 1.87% | 3.37% | 6.58% | 13.7% | 23.5% |

Raised by each condition (hazard ratio), *assumed*: heart failure 2.5, CKD 1.8, type 2 diabetes 1.5, atrial fibrillation 1.5. Hypertension and hyperlipidaemia: none. *Caveat:* the life table already includes the deaths of people with these conditions, so multiplying on top overstates mortality somewhat. Acceptable for plausible fake data; stated here so nobody mistakes it for an estimate.

## 6. Visits

| Visit type | Rate per patient per year | Status |
| --- | --- | --- |
| Outpatient | 0.5 + 1.0 per condition on the problem list | assumed |
| Emergency | 0.15, × 2 with heart failure | assumed |
| Inpatient admission | 4.2% at 18–29 up to 13.5% at 75+, as in section 1; × 2 with heart failure | sourced (by age), assumed (heart-failure factor) |

For comparison, Dutch adults reported 5.1 specialist contacts per person in 2024, 4.3 at 20–30 up to 6.7 at 75+ (CBS 85454NED, self-reported, all specialties). Our outpatient rate counts only visits for these six conditions, so it should be lower.

Inpatient length of stay: 1 to 10 days, more for older patients and heart failure (*assumed*). Nobody has a visit after their date of death.

**Added in week 1, drafted by the assistant for the owner's review** (all *assumed*):

- Inpatient length of stay: a whole number of days from 1 to 10, each equally likely; for patients aged 75+ or admitted for heart failure, the longer of two such draws.
- Outpatient visits start on weekdays between 08:00 and 16:59, on a 5-minute grid, and last 10 to 30 minutes. Emergency visits start at any time and last 1 to 6 hours. Admissions start at any time.
- A visit is for one of the conditions the patient has on that day, each equally likely. A patient with none yet sees internal medicine, and the visit has no diagnosis recorded.
- Diagnoses recorded: the condition the visit is for, as primary. A clinic visit adds the patient's other conditions that the same department treats; an admission adds all their other conditions, as secondary. An emergency visit records only its primary.
- Rates are per year: in the year of death, a patient's expected visits are cut in proportion to the part of the year they were alive.
- 8 clinicians per department, with Dutch Faker names. A visit's clinician is drawn from its department.

## 7. Departments

Each visit goes to the department that treats the condition it is for (*assumed*, following usual Dutch hospital practice):

| Condition | Department |
| --- | --- |
| Type 2 diabetes, hypertension, hyperlipidaemia | Internal medicine |
| Atrial fibrillation, heart failure | Cardiology |
| CKD | Nephrology |
| Emergency visits | Emergency department |

## 8. What this means for the prediction model

The spec's estimate assumed about 35% of patients have hypertension or heart failure. With section 1's age mix and section 2's rates, about **26%** have hypertension at baseline (derived). Keeping the spec's other assumptions (30% with a new start, 70% tested, 8% hyperkalaemia), 25,000 patients give about **108 events, about 76 in training**, short of the 100 needed. About 35,000 patients would give about 106 in training.

Two things push the real count up: co-occurrence (section 3) raises hypertension above the GP rate, and the closed cohort ages ten years over follow-up. So the spec's existing rule stands: count the events after the first full generation, and raise the population if fewer than 100 fall in training.

---

# Week 2: medicines, labs and interactions

> **Drafted by the assistant for the owner's review** (weeks 1–5 were built in one go, by the owner's choice). Nothing below has the owner's approval yet. Numbers are *assumed* unless a source is named. The ATC and LOINC codes are to verify against the official lists; only bare codes are committed (spec, "Data").

## 9. Medicines

One representative medicine per class: metformin (A10BA02), insulin glargine (A10AE04), ramipril (C09AA05), losartan (C09CA01), hydrochlorothiazide (C03AA03), furosemide (C03CA01), spironolactone (C03DA01), metoprolol (C07AB02), warfarin (B01AA03), apixaban (B01AF02), atorvastatin (C10AA05). Doses are usual starting or maintenance doses.

| Condition | Treatment when diagnosed (chance; otherwise none) |
| --- | --- |
| Type 2 diabetes | metformin 85%; insulin 15%, 2–8 years after diagnosis |
| Hypertension | ramipril 50% or losartan 25%; and hydrochlorothiazide 30% |
| Hyperlipidaemia | atorvastatin 70% |
| CKD | ramipril 40% or losartan 20%, unless already on one |
| Atrial fibrillation | warfarin 25% or apixaban 60%; metoprolol 60%, unless already on a beta blocker |
| Heart failure | ramipril 55% or losartan 25%, unless already on one; metoprolol 80%, unless already on one; furosemide 70% |

- Started 0–60 days after diagnosis. A condition already present on 2016-01-01 was treated before the history starts, so its first order is a repeat order in the first 90 days.
- One order covers 90 days and is repeated until the therapy stops: 5% a year stop, and at death or the end of the history.
- Spironolactone is added in heart failure, 8% a year, on top of an ACE inhibitor or ARB.
- An ACE inhibitor is replaced by losartan within 2 years in 10% (cough).
- Metformin: at the first eGFR **result** below 30 during a metformin therapy, 70% stop within 30 days; 30% continue (interaction 4). Decided on the result, as a doctor would (changed in week 5; it was first decided on the true eGFR, which question 3 showed to be wrong).
- A medicine is never started twice at once. Repeat prescriptions have no visit (`encounter_id` empty).
- *Note:* Dutch practice uses acenocoumarol more than warfarin; the spec names warfarin, so the data does.

## 10. Labs

Ten tests, with typical Dutch adult reference ranges: potassium, sodium, creatinine (men 60–110, women 45–90 µmol/L), eGFR, HbA1c (mmol/mol), glucose, LDL, ALT (upper limit men 45, women 35 U/L), INR, NT-proBNP. Values are clipped to physiological limits and rounded as a lab reports them; thresholds apply to the rounded value.

**When:** 80% of outpatient visits order the panel for the condition the visit is for (e.g. diabetes: HbA1c, glucose, creatinine, eGFR, potassium); a visit with no condition: HbA1c, glucose, creatinine, eGFR. Emergency visits and admissions: sodium, potassium, creatinine, eGFR, glucose. Outside visits: potassium, creatinine and eGFR 5–21 days after a RAAS-inhibitor start, in 70% (guidelines advise the check; it does not always happen); ALT 6–12 weeks after a statin start, in 60%; INR every 28 days on warfarin.

**Values:**
- **Kidney:** each patient has a true eGFR course. Without CKD: 105 at age 30, minus 0.8 per year of age, ± 10, falling 0.8 a year, never below 61. With CKD: 15–59 on the start date (or 45–59 at a later diagnosis, falling to it from the healthy value), then falling 1–4 a year. A creatinine is drawn around the value that matches the true eGFR (5% variation), and the reported eGFR is computed from it with the **CKD-EPI 2021** equation (Inker et al., *NEJM* 2021), as a lab does.
- **Potassium:** the patient's own level (4.3 ± 0.35), +0.1 per 10 eGFR below 60, + medicine effects (ACE inhibitor/ARB +0.15, spironolactone +0.3, loop diuretic −0.3, thiazide −0.25), ± 0.2 per test.
- **HbA1c:** 36 ± 3 without diabetes; 62 ± 10 with, falling by 10 on metformin and 8 more on insulin, over 90 days. **Glucose** follows HbA1c by the ADAG relation (Nathan et al., *Diabetes Care* 2008: 0.0915 × HbA1c + 2.15).
- **LDL:** 3.2 ± 0.7, or 4.6 ± 0.8 with hyperlipidaemia; 40% lower on a statin. **Sodium:** 140 ± 2, 2 lower on a diuretic. **ALT:** median 22 U/L. **INR:** 1.0 off warfarin, 2.6 ± 0.45 on it. **NT-proBNP:** median 80 ng/L, 1,500 with heart failure.

## 11. The five interactions, planted

| # | Interaction | Planted as |
| --- | --- | --- |
| 1 | Hyperkalaemia (K⁺ ≥ 5.5) within 30 days of a RAAS-inhibitor start | Once per start, chance from the formula below. If it happens, every potassium in days 1–30 is ≥ 5.5; if not, none is |
| 2 | Hypokalaemia (K⁺ < 3.5) on a loop or thiazide diuretic | 8% of potassium tests on a diuretic (outside interaction 1's windows); the rest ≥ 3.5 |
| 3 | INR > 4 on warfarin | 8% of INR tests on warfarin; the rest 1.0–4.0 |
| 4 | Metformin continued with eGFR < 30 | At the first eGFR result below 30 during a metformin therapy: 30% continue, 70% stop within 30 days |
| 5 | ALT > 3 × upper limit after a statin start | 2% of statin starts, in the first 12 weeks on the statin |

A **start** is an order with no order of the same class (ACE inhibitor, ARB, spironolactone) in the 180 days before, counted from 180 days after the history starts.

**Interaction 1's formula**, the truth the prediction model should recover. Log-odds = −3.4 + 0.30 × (eGFR below 60, per 10) + 1.20 × (potassium − 4.5) + 0.50 × diabetes + 0.25 × (age − 60, per 10 years) + 1.00 × ACE inhibitor or ARB with spironolactone − 0.70 × loop or thiazide diuretic. eGFR and potassium are the most recent results in the 365 days before the start, as the model will see them (the true level if none).

**Outcome counts** (full run, 40,000 patients, seed 20261126, after the week 4 and 5 fixes): 4,251 RAAS starts from 2017; potassium measured within 30 days after 3,064 (72%); 175 observed hyperkalaemia events, so about 122 in a 70% training set (`marts.fact_raas_start`).

What the generator planted is written to `data/truth/raas_start.csv` (never loaded into the database), so tests can check the analysis finds exactly that.
