-- Grain: one row per continuous period a patient takes one medicine.
-- Orders of one medicine that follow on without a gap (the next starts no
-- later than the day after the last one ends) form one period. This is
-- "gaps and islands": flag each order that starts a new period, then number
-- the periods with a running sum of the flags.
with flagged as (
    select
        o.patient_id,
        o.atc_code,
        o.start_date,
        o.stop_date,
        o.medication_order_id,
        -- The first order has no previous one: lag() is null, the comparison
        -- is unknown, and "else 1" starts a period.
        case when o.start_date <= lag(o.stop_date) over w + 1 then 0 else 1 end as starts_period
    from {{ source('ehr', 'medication_order') }} as o
    -- medication_order_id breaks ties, so the order is the same on every run.
    window w as (partition by o.patient_id, o.atc_code order by o.start_date, o.medication_order_id)
),

numbered as (
    select
        *,
        sum(starts_period) over (
            partition by patient_id, atc_code
            order by start_date, medication_order_id
            rows between unbounded preceding and current row
        ) as period
    from flagged
),

periods as (
    select
        p.pseudonym,
        n.atc_code,
        min(n.start_date) as start_date,
        max(n.stop_date) as stop_date,
        count(*) as order_count
    from numbered as n
    inner join {{ ref('stg_patient') }} as p using (patient_id)
    group by p.pseudonym, n.atc_code, n.period
)

select
    row_number() over (order by pseudonym, atc_code, start_date) as exposure_key,
    pseudonym,
    atc_code,
    start_date,
    stop_date,
    {{ date_key('start_date') }} as start_date_key,
    stop_date - start_date + 1 as days_exposed,
    order_count
from periods
