-- Question 1a: how many patients have each condition, by age band and sex?
-- On the start date (2016-01-01), so it can be compared with the rates the
-- generator was given (docs/clinical-rules.md, section 2).
-- The condition flags are columns of dim_patient; "cross join lateral (values ...)"
-- turns each patient's six flags into six rows, one per condition.
select
    c.condition,
    d.age_band_at_start as age_band,
    d.sex,
    count(*) as patients,
    count(*) filter (where c.present) as with_condition,
    round(100.0 * count(*) filter (where c.present) / count(*), 1) as prevalence_pct
from marts.dim_patient as d
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
order by c.condition, d.age_band_at_start, d.sex
