-- Question 1b: which combinations of conditions occur, and how often?
-- On the start date. Each patient's combination is the names of their
-- conditions joined in a fixed order; the most common combinations first.
with combos as (
    select
        concat_ws(' + ',
            case when hypertension_at_start then 'hypertension' end,
            case when hyperlipidaemia_at_start then 'hyperlipidaemia' end,
            case when type2_diabetes_at_start then 'type2_diabetes' end,
            case when ckd_at_start then 'ckd' end,
            case when atrial_fibrillation_at_start then 'atrial_fibrillation' end,
            case when heart_failure_at_start then 'heart_failure' end
        ) as combination
    from marts.dim_patient
)

select
    coalesce(nullif(combination, ''), '(none)') as combination,
    count(*) as patients,
    round(100.0 * count(*) / sum(count(*)) over (), 1) as share_pct
from combos
group by combination
-- combination breaks ties in the count, so the order is the same on every run.
order by patients desc, combination
limit 15
