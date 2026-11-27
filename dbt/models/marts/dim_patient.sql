-- Grain: one row per patient.
-- No name, MRN, exact birth date or address: the pseudonym replaces the ID,
-- age bands replace the birth date (from the birth year: the age reached in
-- that year), and the province replaces the address.
with condition_onsets as (
    select
        c.patient_id,
        d.condition,
        c.onset_date
    from {{ source('ehr', 'condition') }} as c
    inner join {{ ref('dim_diagnosis') }} as d using (icd10_code)
)

select
    p.pseudonym,
    p.sex,
    {{ age_band("extract(year from date '" ~ var('history_start') ~ "') - p.birth_year") }} as age_band_at_start,
    {{ age_band("extract(year from coalesce(p.death_date, date '" ~ var('reference_date') ~ "')) - p.birth_year") }}
        as age_band_at_end,
    i.province as region,
    p.death_date,
    p.death_date is not null as is_deceased,
    {%- for condition in conditions() %}
    -- On the problem list on the start date, and by the end of the history.
    exists (
        select 1 from condition_onsets as o
        where o.patient_id = p.patient_id and o.condition = '{{ condition }}'
            and o.onset_date < date '{{ var("history_start") }}'
    ) as {{ condition }}_at_start,
    exists (
        select 1 from condition_onsets as o
        where o.patient_id = p.patient_id and o.condition = '{{ condition }}'
    ) as has_{{ condition }}{% if not loop.last %},{% endif %}
    {%- endfor %}
from {{ ref('stg_patient') }} as p
inner join {{ source('ehr_identity', 'patient_identity') }} as i using (patient_id)
