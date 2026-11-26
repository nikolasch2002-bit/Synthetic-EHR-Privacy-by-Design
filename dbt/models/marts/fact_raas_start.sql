-- Grain: one row per start of a RAAS inhibitor (the index date), from
-- 2017-01-01, so every start has a year of history before it.
-- The prediction model's cohort (spec, "Prediction model"): its features,
-- known before the index date only; the rule baseline score; and the
-- outcome, hyperkalaemia (K+ >= 5.5) on days 1-30 after the index date.
with starts as (
    select
        s.*,
        p.pseudonym,
        p.sex,
        -- From the birth year: the age reached in the index year.
        extract(year from s.index_date)::int - p.birth_year as age
    from {{ ref('stg_raas_start') }} as s
    inner join {{ ref('stg_patient') }} as p using (patient_id)
    where s.index_date >= date '2017-01-01'
),

labs as (
    select o.patient_id, t.test_name, o.ordered_at, o.lab_order_id, r.value
    from {{ source('ehr', 'lab_order') }} as o
    inner join {{ source('ehr', 'lab_result') }} as r using (lab_order_id)
    inner join {{ ref('dim_lab_test') }} as t using (loinc_code)
    where t.test_name in ('egfr', 'potassium')
),

-- The most recent eGFR and potassium in the 365 days before the index date
-- (not on it). distinct on keeps the first row per start and test: the
-- latest, with lab_order_id breaking ties so the pick is the same every run.
baseline as (
    select distinct on (s.patient_id, s.drug_class, s.index_date, l.test_name)
        s.patient_id, s.drug_class, s.index_date, l.test_name, l.value, l.ordered_at::date as day
    from starts as s
    inner join labs as l
        on l.patient_id = s.patient_id
        and l.ordered_at::date < s.index_date
        and l.ordered_at::date >= s.index_date - 365
    order by s.patient_id, s.drug_class, s.index_date, l.test_name, l.ordered_at desc, l.lab_order_id desc
),

-- Potassium on days 1-30 after the index date: the outcome window.
outcome as (
    select
        s.patient_id, s.drug_class, s.index_date,
        max(l.value) as highest_potassium
    from starts as s
    inner join labs as l
        on l.patient_id = s.patient_id
        and l.test_name = 'potassium'
        and l.ordered_at::date - s.index_date between 1 and 30
    group by s.patient_id, s.drug_class, s.index_date
),

-- Medicine classes covered by an order on the index date.
on_index as (
    select s.patient_id, s.drug_class, s.index_date, d.drug_class as class_on_index
    from starts as s
    inner join {{ source('ehr', 'medication_order') }} as o
        on o.patient_id = s.patient_id
        and s.index_date between o.start_date and o.stop_date
    inner join {{ ref('dim_drug') }} as d on d.atc_code = o.atc_code
),

conditions as (
    select c.patient_id, d.condition, c.onset_date
    from {{ source('ehr', 'condition') }} as c
    inner join {{ ref('dim_diagnosis') }} as d using (icd10_code)
),

features as (
    select
        s.pseudonym,
        s.drug_class,
        s.atc_code,
        s.index_date,
        s.sex,
        s.age,
        e.value as egfr_before,
        e.day as egfr_before_date,
        k.value as potassium_before,
        k.day as potassium_before_date,
        exists (
            select 1 from conditions as c
            where c.patient_id = s.patient_id and c.condition = 'type2_diabetes' and c.onset_date <= s.index_date
        ) as diabetes,
        exists (
            select 1 from conditions as c
            where c.patient_id = s.patient_id and c.condition = 'heart_failure' and c.onset_date <= s.index_date
        ) as heart_failure,
        exists (
            select 1 from conditions as c
            where c.patient_id = s.patient_id and c.condition = 'ckd' and c.onset_date <= s.index_date
        ) as ckd,
        -- An ACE inhibitor or ARB together with spironolactone on the index date.
        exists (
            select 1 from on_index as i
            where (i.patient_id, i.drug_class, i.index_date) = (s.patient_id, s.drug_class, s.index_date)
                and i.class_on_index in ('ace_inhibitor', 'arb')
        ) and exists (
            select 1 from on_index as i
            where (i.patient_id, i.drug_class, i.index_date) = (s.patient_id, s.drug_class, s.index_date)
                and i.class_on_index = 'mra'
        ) as combination,
        exists (
            select 1 from on_index as i
            where (i.patient_id, i.drug_class, i.index_date) = (s.patient_id, s.drug_class, s.index_date)
                and i.class_on_index in ('loop_diuretic', 'thiazide')
        ) as loop_or_thiazide,
        o.highest_potassium
    from starts as s
    left join baseline as e
        on (e.patient_id, e.drug_class, e.index_date, e.test_name) = (s.patient_id, s.drug_class, s.index_date, 'egfr')
    left join baseline as k
        on (k.patient_id, k.drug_class, k.index_date, k.test_name)
        = (s.patient_id, s.drug_class, s.index_date, 'potassium')
    left join outcome as o
        on (o.patient_id, o.drug_class, o.index_date) = (s.patient_id, s.drug_class, s.index_date)
)

select
    row_number() over (order by pseudonym, index_date, drug_class) as raas_start_key,
    pseudonym,
    drug_class,
    atc_code,
    index_date,
    {{ date_key('index_date') }} as index_date_key,
    sex,
    age,
    egfr_before,
    egfr_before_date,
    egfr_before is null as egfr_missing,
    potassium_before,
    potassium_before_date,
    potassium_before is null as potassium_missing,
    diabetes,
    heart_failure,
    ckd,
    combination,
    loop_or_thiazide,
    -- The rule baseline: one point each. Invented for this project, not a
    -- published score. A missing result scores 0 for its item.
    (coalesce(egfr_before < 45, false))::int
    + (coalesce(potassium_before > 5.0, false))::int
    + combination::int
    + diabetes::int
    + (age >= 75)::int as rule_score,
    highest_potassium is not null as potassium_measured,
    -- Not measured is not the same as normal: no potassium, no outcome.
    case when highest_potassium is not null then highest_potassium >= 5.5 end as hyperkalaemia
from features
