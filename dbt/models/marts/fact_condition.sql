-- Grain: one row per condition on a patient's problem list.
select
    p.pseudonym,
    c.icd10_code,
    c.onset_date,
    {{ date_key('c.onset_date') }} as onset_date_key,
    c.onset_date < date '{{ var("history_start") }}' as present_at_start
from {{ source('ehr', 'condition') }} as c
inner join {{ ref('stg_patient') }} as p using (patient_id)
