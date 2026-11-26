-- Question 7: data quality. Each check counts rows that should not exist;
-- every count is expected to be 0, and a test fails if one is not.
select 'fact rows whose patient is not in dim_patient' as check_name, count(*) as failing_rows
from (
    select pseudonym from marts.fact_encounter
    union all select pseudonym from marts.fact_lab_result
    union all select pseudonym from marts.fact_condition
    union all select pseudonym from marts.fact_medication_exposure
) as f
where not exists (select 1 from marts.dim_patient as p where p.pseudonym = f.pseudonym)

union all
select 'visits after death', count(*)
from marts.fact_encounter as e
inner join marts.dim_patient as p using (pseudonym)
where e.start_time::date > p.death_date

union all
select 'diagnoses after death', count(*)
from marts.fact_condition as c
inner join marts.dim_patient as p using (pseudonym)
where c.onset_date > p.death_date

union all
select 'medicine periods starting after death', count(*)
from marts.fact_medication_exposure as m
inner join marts.dim_patient as p using (pseudonym)
where m.start_date > p.death_date

union all
select 'lab tests after death', count(*)
from marts.fact_lab_result as r
inner join marts.dim_patient as p using (pseudonym)
where r.ordered_at::date > p.death_date

union all
select 'visits before the history starts', count(*)
from marts.fact_encounter
where start_time < date '2016-01-01'

union all
select 'visits ending before they start', count(*)
from marts.fact_encounter
where end_time < start_time

union all
select 'lab values outside physiological limits', count(*)
from marts.fact_lab_result as r
inner join marts.dim_lab_test as t using (loinc_code)
where r.value < t.limit_low or r.value > t.limit_high

union all
select 'lab results on a visit of another patient', count(*)
from marts.fact_lab_result as r
inner join marts.fact_encounter as e using (encounter_key)
where r.pseudonym <> e.pseudonym

union all
select 'date keys that disagree with their timestamp', count(*)
from marts.fact_encounter
where start_date_key <> to_char(start_time, 'YYYYMMDD')::int
