-- Grants and row-level security on the source schemas. Run by the loader in
-- the same transaction as the load: the loader drops and recreates these
-- tables, which removes anything attached to them, so their protections are
-- made in the same step (docs/lessons-learned.md). Never added afterwards.

-- Who treats whom: a clinician role and the patients with at least one visit
-- in its department. Rebuilt with every load. A clinician sees the full
-- record of these patients, and nothing of anyone else.
drop table if exists security.care_relation;
create table security.care_relation as
select distinct
    e.patient_id,
    ('clinician_' || d.code)::name as role_name
from ehr.encounter as e
inner join ehr.department as d on d.department_id = e.department_id;
alter table security.care_relation add primary key (role_name, patient_id);

-- A clinician reads only its own rows of care_relation (role_name is the
-- current role). So, below, "exists a care_relation row for this patient"
-- means "this patient is mine", with no function that could be called to
-- probe other departments.
alter table security.care_relation enable row level security;
create policy own_rows on security.care_relation for select
    using (role_name = current_user);
create policy steward_and_etl on security.care_relation for all to data_steward, etl
    using (true) with check (true);

do $$
declare
    clinicians text;
    t text;
begin
    -- Every clinician role, one per department, as a comma-separated list.
    select string_agg(quote_ident('clinician_' || code), ', ')
    into clinicians
    from ehr.department;

    execute format('grant usage on schema security to %s', clinicians);
    execute format('grant select on security.care_relation to %s', clinicians);
    -- etl writes care_relation, so it may use the schema; the audit log in
    -- the same schema stays closed to it by that table's own revoke (roles.sql).
    execute 'grant usage on schema security to etl';
    execute 'grant all on security.care_relation to etl';

    execute format('grant usage on schema ehr, ehr_identity to %s, data_steward, etl', clinicians);
    execute format('grant select on all tables in schema ehr, ehr_identity to %s, data_steward', clinicians);
    execute 'grant select, insert, update, delete on all tables in schema ehr, ehr_identity to etl';

    -- Tables with a patient_id: row-level security by care relation.
    foreach t in array array[
        'ehr.patient', 'ehr.condition', 'ehr.encounter', 'ehr.medication_order',
        'ehr.lab_order', 'ehr_identity.patient_identity'
    ] loop
        execute format('alter table %s enable row level security', t);
        execute format(
            'create policy own_patients on %s for select to %s using ('
            'exists (select 1 from security.care_relation as c where c.patient_id = %s.patient_id))',
            t, clinicians, t
        );
        execute format(
            'create policy steward_and_etl on %s for all to data_steward, etl using (true) with check (true)', t
        );
    end loop;

    -- Tables keyed to a visit or an order: visible when their parent row is.
    -- The subquery is itself filtered by the parent table's policy.
    execute 'alter table ehr.encounter_diagnosis enable row level security';
    execute format(
        'create policy own_patients on ehr.encounter_diagnosis for select to %s using ('
        'exists (select 1 from ehr.encounter as e where e.encounter_id = encounter_diagnosis.encounter_id))',
        clinicians
    );
    execute 'alter table ehr.lab_result enable row level security';
    execute format(
        'create policy own_patients on ehr.lab_result for select to %s using ('
        'exists (select 1 from ehr.lab_order as o where o.lab_order_id = lab_result.lab_order_id))',
        clinicians
    );
    foreach t in array array['ehr.encounter_diagnosis', 'ehr.lab_result'] loop
        execute format(
            'create policy steward_and_etl on %s for all to data_steward, etl using (true) with check (true)', t
        );
    end loop;
end $$;
