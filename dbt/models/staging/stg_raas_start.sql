-- One row per start of a RAAS inhibitor (ACE inhibitor, ARB, spironolactone):
-- an order with no order of the same class in the 180 days before
-- (spec, "Prediction model"). Counted from 180 days into the history, when
-- those 180 days are in the data. Ephemeral: it holds patient_id.
with raas_orders as (
    select
        o.patient_id,
        o.medication_order_id,
        o.atc_code,
        d.drug_class,
        o.start_date,
        -- The previous order of the same class; medication_order_id breaks ties.
        lag(o.start_date) over (
            partition by o.patient_id, d.drug_class
            order by o.start_date, o.medication_order_id
        ) as previous_start
    from {{ source('ehr', 'medication_order') }} as o
    inner join {{ ref('dim_drug') }} as d using (atc_code)
    where d.drug_class in ('ace_inhibitor', 'arb', 'mra')
)

select
    patient_id,
    drug_class,
    atc_code,
    start_date as index_date
from raas_orders
where
    (previous_start is null or start_date - previous_start > 180)
    and start_date >= date '{{ var("history_start") }}' + 180
