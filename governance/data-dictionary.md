# Data dictionary

Every table and column in the source schemas: what it means, its type, the values it allows, its personal-data class, and which roles may read it. A test (`tests/test_database.py`) compares this file with the database and fails if a column is in one and not the other, or if a type differs.

**Personal-data classes:** *direct identifier*: identifies a person on its own (name, MRN, address, exact birth date); *quasi-identifier*: could identify a person when combined with others (birth year, sex, dates of care); *health data*: a special category under GDPR Art. 9; *none*.

**Roles** (spec, "Security and compliance deliverables"; enforced from week 7): `clinician_<dept>` reads the identifiable record of its own department's patients; `data_steward` reads everything and can re-link pseudonyms; `etl` writes; `researcher` and `public_app` read **no** source table, only the marts. Below, "clinical roles" means `clinician_<dept>`, `data_steward` and `etl`.

The data is entirely fake, and treated as if it were real.

## Schema `ehr_identity`

### `ehr_identity.patient_identity`

One row per patient: the only place identifiers live. Read by: `clinician_<dept>` (own department's patients), `data_steward`, `etl`.

| Column | Type | Meaning | Allowed values | Personal data |
| --- | --- | --- | --- | --- |
| `patient_id` | integer | Internal patient key, the same as `ehr.patient` | an existing `ehr.patient` | quasi-identifier |
| `mrn` | text | Medical record number | `SYN-` and 7 digits; unique | direct identifier |
| `given_name` | text | Given name (Faker, Dutch) | any | direct identifier |
| `family_name` | text | Family name (Faker, Dutch) | any | direct identifier |
| `birth_date` | date | Exact date of birth | any | direct identifier |
| `sex` | char(1) | Sex | `F`, `M` | quasi-identifier |
| `street_address` | text | Street and house number | any | direct identifier |
| `postcode` | text | Postcode | Dutch format, e.g. `1234AB` | direct identifier |
| `city` | text | City | any | quasi-identifier |
| `province` | text | Province; drawn apart from the city | the 12 Dutch provinces | quasi-identifier |

## Schema `ehr`

Read by: the clinical roles (`clinician_<dept>` only for its own department's patients, from week 7).

### `ehr.patient`

One row per patient.

| Column | Type | Meaning | Allowed values | Personal data |
| --- | --- | --- | --- | --- |
| `patient_id` | integer | Internal patient key; means nothing outside this database | unique | quasi-identifier |
| `sex` | char(1) | Sex | `F`, `M` | quasi-identifier |
| `birth_year` | smallint | Year of birth (the exact date is in `ehr_identity`) | 1900–2010 | quasi-identifier |
| `death_date` | date | Date of death; empty if alive on the reference date | on or after the birth year | health data |

### `ehr.department`

One row per hospital department.

| Column | Type | Meaning | Allowed values | Personal data |
| --- | --- | --- | --- | --- |
| `department_id` | smallint | Department key | unique | none |
| `code` | text | Short code | unique, e.g. `cardiology` | none |
| `name` | text | Display name | any | none |

### `ehr.clinician`

One row per clinician.

| Column | Type | Meaning | Allowed values | Personal data |
| --- | --- | --- | --- | --- |
| `clinician_id` | integer | Clinician key | unique | none |
| `department_id` | smallint | The department the clinician works in | an existing department | none |
| `given_name` | text | Given name (Faker, Dutch) | any | direct identifier (of staff) |
| `family_name` | text | Family name (Faker, Dutch) | any | direct identifier (of staff) |

### `ehr.condition`

One row per condition on a patient's problem list.

| Column | Type | Meaning | Allowed values | Personal data |
| --- | --- | --- | --- | --- |
| `condition_id` | bigint | Condition key (patient ID × 100 + a counter) | unique | none |
| `patient_id` | integer | The patient | an existing patient | quasi-identifier |
| `icd10_code` | text | Diagnosis, ICD-10 (WHO, 2019) | an `ehr.icd10_code`; at most once per patient | health data |
| `onset_date` | date | Date of diagnosis | any | health data |
| `resolved_date` | date | Date resolved; empty: all six conditions are chronic | on or after onset | health data |

### `ehr.encounter`

One row per visit.

| Column | Type | Meaning | Allowed values | Personal data |
| --- | --- | --- | --- | --- |
| `encounter_id` | bigint | Visit key (patient ID × 10,000 + a counter) | unique | none |
| `patient_id` | integer | The patient | an existing patient | quasi-identifier |
| `department_id` | smallint | Department visited | an existing department | health data |
| `clinician_id` | integer | Clinician seen | a clinician of that department | none |
| `encounter_type` | text | Kind of visit | `outpatient`, `emergency`, `inpatient` | health data |
| `start_time` | timestamp | Start (admission, for inpatients) | any | quasi-identifier |
| `end_time` | timestamp | End (discharge) | at or after the start | quasi-identifier |

### `ehr.encounter_diagnosis`

One row per diagnosis recorded at a visit.

| Column | Type | Meaning | Allowed values | Personal data |
| --- | --- | --- | --- | --- |
| `encounter_id` | bigint | The visit | an existing visit | none |
| `icd10_code` | text | Diagnosis, ICD-10 | an `ehr.icd10_code`; once per visit | health data |
| `is_primary` | boolean | The diagnosis the visit was for | at most one `true` per visit | health data |

### `ehr.medication_order`

One row per prescription; each covers up to 90 days.

| Column | Type | Meaning | Allowed values | Personal data |
| --- | --- | --- | --- | --- |
| `medication_order_id` | bigint | Order key (patient ID × 10,000 + a counter) | unique | none |
| `patient_id` | integer | The patient | an existing patient | quasi-identifier |
| `encounter_id` | bigint | The visit it was ordered at; empty for repeat prescriptions | the same patient's visit | none |
| `atc_code` | text | Medicine, ATC | an `ehr.atc_code` | health data |
| `dose` | numeric | Dose per intake | above 0 | health data |
| `dose_unit` | text | Unit of the dose | `mg`, `units` | health data |
| `frequency` | text | How often | `once daily`, `twice daily` | health data |
| `start_date` | date | First day covered | any | health data |
| `stop_date` | date | Last day covered | on or after the start | health data |

### `ehr.lab_order`

One row per lab test ordered.

| Column | Type | Meaning | Allowed values | Personal data |
| --- | --- | --- | --- | --- |
| `lab_order_id` | bigint | Order key (patient ID × 100,000 + a counter) | unique | none |
| `patient_id` | integer | The patient | an existing patient | quasi-identifier |
| `encounter_id` | bigint | The visit; empty for follow-up and monitoring tests | the same patient's visit | none |
| `loinc_code` | text | Test, LOINC | an `ehr.loinc_code` | health data |
| `ordered_at` | timestamp | When ordered (and drawn) | any | quasi-identifier |

### `ehr.lab_result`

One row per result; one result per order.

| Column | Type | Meaning | Allowed values | Personal data |
| --- | --- | --- | --- | --- |
| `lab_order_id` | bigint | The order | an existing order | none |
| `value` | numeric | Result, rounded as reported | within the test's physiological limits | health data |
| `unit` | text | Unit | the test's unit, e.g. `mmol/L` | none |
| `reference_low` | numeric | Lower reference limit (sex-specific where it differs) | below `reference_high` | none |
| `reference_high` | numeric | Upper reference limit | above `reference_low` | none |
| `resulted_at` | timestamp | When the result was reported | after `ordered_at` | quasi-identifier |

### Code tables: `ehr.icd10_code`, `ehr.atc_code`, `ehr.loinc_code`

One row per code. Bare codes only, until the owner has read each code set's terms (spec, "Data"). Read by: everyone, including `researcher` (as `dim_*` tables in the marts).

| Column | Type | Meaning | Allowed values | Personal data |
| --- | --- | --- | --- | --- |
| `ehr.icd10_code.code` | text | ICD-10 code (WHO, 2019) | e.g. `E11` | none |
| `ehr.atc_code.code` | text | ATC code (WHO Collaborating Centre) | e.g. `C09AA05` | none |
| `ehr.loinc_code.code` | text | LOINC code (Regenstrief Institute) | e.g. `2823-3` | none |
