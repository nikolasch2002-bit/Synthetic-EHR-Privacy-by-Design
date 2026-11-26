-- Grain: one row per visit.
select
    k.encounter_key,
    p.pseudonym,
    e.department_id,
    e.encounter_type,
    {{ date_key('e.start_time') }} as start_date_key,
    e.start_time,
    e.end_time,
    round(extract(epoch from (e.end_time - e.start_time)) / 3600, 2) as length_hours,
    count(d.icd10_code) as diagnosis_count,
    max(d.icd10_code) filter (where d.is_primary) as primary_icd10_code
from {{ source('ehr', 'encounter') }} as e
inner join {{ ref('stg_patient') }} as p using (patient_id)
inner join {{ ref('stg_encounter_key') }} as k using (encounter_id)
left join {{ source('ehr', 'encounter_diagnosis') }} as d using (encounter_id)
group by k.encounter_key, p.pseudonym, e.department_id, e.encounter_type, e.start_time, e.end_time
