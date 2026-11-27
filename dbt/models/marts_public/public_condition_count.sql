-- Grain: one row per condition, age band (in 2016) and sex: the number of
-- patients with the condition on 2016-01-01. Suppressed below k. No totals
-- are published, so a hidden count cannot be worked out by subtraction.
with counts as (
    select
        c.condition,
        d.age_band_at_start as age_band,
        d.sex,
        count(*) filter (where c.present) as patients
    from {{ ref('dim_patient') }} as d
    -- Six flag columns turned into six rows, one per condition.
    cross join lateral (
        values
            ('hypertension', d.hypertension_at_start),
            ('hyperlipidaemia', d.hyperlipidaemia_at_start),
            ('type2_diabetes', d.type2_diabetes_at_start),
            ('ckd', d.ckd_at_start),
            ('atrial_fibrillation', d.atrial_fibrillation_at_start),
            ('heart_failure', d.heart_failure_at_start)
    ) as c (condition, present)
    group by c.condition, d.age_band_at_start, d.sex
)

select
    condition,
    age_band,
    sex,
    {{ suppress('patients') }} as patients,
    {{ is_suppressed('patients') }} as is_suppressed
from counts
