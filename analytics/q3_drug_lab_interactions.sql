-- Question 3: for each drug-lab rule, how often does it happen, against the
-- rate the generator planted, and how soon after the medicine starts?
-- Each rule is counted the way it was planted:
--   per test:  results on the medicine that break the rule / results on it;
--   per start: starts with a breaking result in the window / starts with a
--              result in the window;
--   per user:  metformin users with an eGFR below 30 who still take it
--              30 days later / users with an eGFR below 30 on metformin.
with rules as (
    select rule, max(planted_rate) as planted_rate, max(planted_per) as planted_per
    from marts.dim_drug_lab_rule
    group by rule
),

per_test as (
    select rule, count(*) as denominator, count(*) filter (where rule_triggered) as events
    from marts.fact_drug_lab_event
    where rule in ('hypokalaemia_on_diuretic', 'inr_above_4_on_warfarin')
    group by rule
),

-- A start is identified by patient, medicine and its start date.
starts as (
    select rule, pseudonym, atc_code, ordered_at::date - days_since_start as start_date,
        bool_or(rule_triggered) as triggered
    from marts.fact_drug_lab_event
    where rule in ('hyperkalaemia_after_raas_start', 'alt_after_statin_start')
    group by rule, pseudonym, atc_code, ordered_at::date - days_since_start
),

per_start as (
    select rule, count(*) as denominator, count(*) filter (where triggered) as events
    from starts
    group by rule
),

-- The first eGFR below 30 in each metformin period. Periods where the
-- patient died, or the history ended, within 31 days of it are left out:
-- whether they continued cannot be seen.
low_egfr as (
    select
        f.pseudonym,
        f.ordered_at::date - f.days_since_start as period_start,
        min(f.ordered_at::date) as first_low
    from marts.fact_drug_lab_event as f
    where f.rule = 'metformin_with_egfr_below_30' and f.rule_triggered
    group by f.pseudonym, f.ordered_at::date - f.days_since_start
),

per_user as (
    select
        'metformin_with_egfr_below_30' as rule,
        count(*) as denominator,
        -- Continued: the same period runs past 30 days after the result.
        count(*) filter (where e.stop_date > l.first_low + 30) as events
    from low_egfr as l
    inner join marts.fact_medication_exposure as e
        on e.pseudonym = l.pseudonym
        and e.start_date = l.period_start
        and e.atc_code = (select atc_code from marts.dim_drug where drug_name = 'metformin')
    inner join marts.dim_patient as p on p.pseudonym = l.pseudonym
    where l.first_low + 31 <= date '2025-12-31'
        and (p.death_date is null or p.death_date > l.first_low + 31)
),

timing as (
    select
        rule,
        percentile_cont(0.5) within group (order by days_since_start) as median_days
    from marts.fact_drug_lab_event
    where rule_triggered
    group by rule
)

select
    r.rule,
    r.planted_per as counted_per,
    c.denominator,
    c.events,
    round(100.0 * c.events / nullif(c.denominator, 0), 2) as rate_pct,
    round(100 * r.planted_rate, 2) as planted_pct,
    round(t.median_days::numeric, 0) as median_days_since_start
from rules as r
inner join (
    select * from per_test
    union all select * from per_start
    union all select * from per_user
) as c using (rule)
left join timing as t using (rule)
order by r.rule
