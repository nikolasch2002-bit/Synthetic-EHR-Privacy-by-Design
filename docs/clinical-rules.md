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
