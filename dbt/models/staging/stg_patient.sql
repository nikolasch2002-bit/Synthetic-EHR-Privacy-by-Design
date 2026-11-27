-- One row per patient, with the pseudonym beside the internal ID. Ephemeral:
-- the marts select from it, but never select patient_id itself.
select
    l.pseudonym,
    p.patient_id,
    p.sex,
    p.birth_year,
    p.death_date
from {{ source('ehr', 'patient') }} as p
inner join {{ source('ehr_link', 'patient_pseudonym') }} as l using (patient_id)
