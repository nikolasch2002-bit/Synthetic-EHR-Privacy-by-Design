-- encounter_id encodes patient_id (patient ID x 10,000 + a counter), so it
-- must not reach the marts: anyone with the source tables could use it to
-- link mart rows back to a person without the key. The marts get a new key
-- instead, numbered in pseudonym order, so linking back needs the key too.
-- encounter_id breaks ties only between one patient's visits at one moment.
select
    e.encounter_id,
    row_number() over (order by p.pseudonym, e.start_time, e.encounter_id) as encounter_key
from {{ source('ehr', 'encounter') }} as e
inner join {{ ref('stg_patient') }} as p using (patient_id)
