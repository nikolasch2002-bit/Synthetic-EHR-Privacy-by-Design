-- Question 6: how does HbA1c change in the year after metformin starts?
-- A start: a metformin exposure period beginning at least 180 days into the
-- history (earlier ones may be treatment that began before the data does).
-- Before: the most recent HbA1c in the 365 days before the start.
-- After: the mean HbA1c from 90 to 365 days after, once the effect has built up.
with starts as (
    select e.pseudonym, e.start_date
    from marts.fact_medication_exposure as e
    inner join marts.dim_drug as d using (atc_code)
    where d.drug_name = 'metformin'
        and e.start_date >= date '2016-01-01' + 180
),

hba1c as (
    select r.pseudonym, r.ordered_at::date as day, r.value, r.lab_result_key
    from marts.fact_lab_result as r
    inner join marts.dim_lab_test as t using (loinc_code)
    where t.test_name = 'hba1c'
),

before as (
    -- distinct on keeps the first row per start: the latest result, with
    -- lab_result_key breaking ties so the pick is the same on every run.
    select distinct on (s.pseudonym, s.start_date)
        s.pseudonym, s.start_date, h.value
    from starts as s
    inner join hba1c as h
        on h.pseudonym = s.pseudonym
        and h.day < s.start_date
        and h.day >= s.start_date - 365
    order by s.pseudonym, s.start_date, h.day desc, h.lab_result_key desc
),

after as (
    select s.pseudonym, s.start_date, avg(h.value) as value
    from starts as s
    inner join hba1c as h
        on h.pseudonym = s.pseudonym
        and h.day between s.start_date + 90 and s.start_date + 365
    group by s.pseudonym, s.start_date
)

select
    (select count(*) from starts) as metformin_starts,
    count(*) as with_hba1c_before_and_after,
    round(avg(b.value), 1) as mean_before,
    round(avg(a.value), 1) as mean_after,
    round(avg(a.value - b.value), 1) as mean_change,
    round(percentile_cont(0.5) within group (order by a.value - b.value)::numeric, 1) as median_change
from before as b
inner join after as a using (pseudonym, start_date)
