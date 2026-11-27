-- Roles and the objects that belong to no rebuilt table (CLAUDE.md: created by
-- a script before the loader and dbt run). Safe to run again: it creates what
-- is missing and replaces functions, and never drops data.
--
-- The roles have no login. A person or the app logs in with its own user and
-- is a member of one role; the tests take on a role with SET ROLE.
-- The access each role gets is in governance/access-control.md.

do $$
declare
    role_name text;
begin
    foreach role_name in array array[
        'clinician_internal_medicine', 'clinician_cardiology', 'clinician_nephrology',
        'clinician_emergency', 'researcher', 'data_steward', 'public_app', 'etl'
    ] loop
        if not exists (select 1 from pg_roles where rolname = role_name) then
            execute format('create role %I nologin', role_name);
        end if;
    end loop;
end $$;

create schema if not exists security;

-- The audit log of re-linking: who looked up which pseudonym's identity, and
-- when. Persistent: no load or build ever drops it.
create table if not exists security.relink_log (
    relink_id bigint generated always as identity primary key,
    relinked_at timestamptz not null default now(),
    -- current_user here is the role that called security.relink(), because
    -- the function runs as its caller (security invoker).
    relinked_by text not null default current_user,
    pseudonym text not null
);

-- Re-linking: the data steward gives a pseudonym and gets the identity back,
-- and the log gets a row. It runs as its caller, so the log records who it
-- really was, and a caller without the steward's rights gets an error.
create or replace function security.relink(p_pseudonym text)
returns table (patient_id integer, mrn text, given_name text, family_name text)
language plpgsql
security invoker
as $$
#variable_conflict use_column
begin
    insert into security.relink_log (pseudonym) values (p_pseudonym);
    return query
        select i.patient_id, i.mrn, i.given_name, i.family_name
        from ehr_link.patient_pseudonym as l
        inner join ehr_identity.patient_identity as i on i.patient_id = l.patient_id
        where l.pseudonym = p_pseudonym;
end $$;

-- These objects outlive every load and build, and so would any grant once
-- made on them. So first take every right away from everyone, then give
-- exactly the intended ones: running this script always ends in the same
-- state, even after a wrong grant was made and later removed from the script.
revoke all on function security.relink(text) from public, clinician_internal_medicine,
    clinician_cardiology, clinician_nephrology, clinician_emergency, researcher,
    data_steward, public_app, etl;
revoke all on security.relink_log from public, clinician_internal_medicine,
    clinician_cardiology, clinician_nephrology, clinician_emergency, researcher,
    data_steward, public_app, etl;

-- Only the steward may re-link (functions are executable by everyone unless revoked).
grant execute on function security.relink(text) to data_steward;
grant usage on schema security to data_steward;
-- The steward can read and add to the log, never change or delete it.
grant select, insert on security.relink_log to data_steward;
