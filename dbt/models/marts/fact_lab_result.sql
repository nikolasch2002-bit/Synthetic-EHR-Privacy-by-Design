-- Grain: one row per lab result.
select
    -- A new key in pseudonym order, for the same reason as encounter_key.
    row_number() over (order by p.pseudonym, o.ordered_at, o.loinc_code, o.lab_order_id) as lab_result_key,
    p.pseudonym,
    k.encounter_key,
    o.loinc_code,
    {{ date_key('o.ordered_at') }} as date_key,
    o.ordered_at,
    r.value,
    r.unit,
    r.reference_low,
    r.reference_high,
    -- "is true" turns an unknown comparison (no limit on that side) into false.
    (r.value < r.reference_low or r.value > r.reference_high) is true as is_abnormal
from {{ source('ehr', 'lab_order') }} as o
inner join {{ source('ehr', 'lab_result') }} as r using (lab_order_id)
inner join {{ ref('stg_patient') }} as p using (patient_id)
left join {{ ref('stg_encounter_key') }} as k using (encounter_id)
