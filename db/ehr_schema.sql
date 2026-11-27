-- The source schemas, normalized (3NF), the way an EHR records care.
--
-- ehr_identity holds the identifiers (name, exact birth date, address, MRN),
-- and only it does (trust boundary 1). ehr holds the clinical record, keyed
-- by an internal patient_id that means nothing outside this database.
--
-- The loader runs this file on every load: the data is regenerated from the
-- seed, so the schemas are rebuilt from empty rather than migrated.

drop schema if exists ehr_identity cascade;
drop schema if exists ehr cascade;
create schema ehr;
create schema ehr_identity;

-- Code tables: bare codes only, until the owner has read each code set's
-- terms (spec, "Data"). The patterns reject anything that is not a code.
create table ehr.icd10_code (
    code text primary key check (code ~ '^[A-Z][0-9]{2}(\.[0-9]{1,2})?$')
);
create table ehr.atc_code (
    code text primary key check (code ~ '^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$')
);
create table ehr.loinc_code (
    code text primary key check (code ~ '^[0-9]{1,7}-[0-9]$')
);

create table ehr.patient (
    patient_id integer primary key,
    sex char(1) not null check (sex in ('F', 'M')),
    -- Only the year: the exact date is an identifier, kept in ehr_identity.
    birth_year smallint not null check (birth_year between 1900 and 2010),
    death_date date check (death_date >= make_date(birth_year, 1, 1))
);

create table ehr_identity.patient_identity (
    patient_id integer primary key references ehr.patient,
    -- SYN-: a format no real person's record number can have.
    mrn text not null unique check (mrn ~ '^SYN-[0-9]{7}$'),
    given_name text not null,
    family_name text not null,
    birth_date date not null,
    sex char(1) not null check (sex in ('F', 'M')),
    street_address text not null,
    postcode text not null,
    city text not null,
    province text not null
);

create table ehr.department (
    department_id smallint primary key,
    code text not null unique,
    name text not null
);

create table ehr.clinician (
    clinician_id integer primary key,
    department_id smallint not null references ehr.department,
    given_name text not null,
    family_name text not null,
    -- Lets ehr.encounter check that its clinician works in its department.
    unique (clinician_id, department_id)
);

create table ehr.condition (
    condition_id bigint primary key,
    patient_id integer not null references ehr.patient,
    icd10_code text not null references ehr.icd10_code,
    onset_date date not null,
    resolved_date date check (resolved_date >= onset_date),
    -- A condition is on a patient's problem list at most once.
    unique (patient_id, icd10_code)
);

create table ehr.encounter (
    encounter_id bigint primary key,
    patient_id integer not null references ehr.patient,
    department_id smallint not null references ehr.department,
    clinician_id integer not null,
    encounter_type text not null check (encounter_type in ('outpatient', 'emergency', 'inpatient')),
    start_time timestamp not null,
    end_time timestamp not null check (end_time >= start_time),
    -- The clinician must work in the visit's department: a two-column foreign
    -- key onto clinician's (clinician_id, department_id) pair.
    foreign key (clinician_id, department_id) references ehr.clinician (clinician_id, department_id),
    -- Lets orders check that their encounter is the same patient's.
    unique (encounter_id, patient_id)
);

create table ehr.encounter_diagnosis (
    encounter_id bigint not null references ehr.encounter,
    icd10_code text not null references ehr.icd10_code,
    is_primary boolean not null,
    primary key (encounter_id, icd10_code)
);
-- At most one primary diagnosis per visit: a unique index over only the
-- primary rows (a partial index).
create unique index encounter_diagnosis_one_primary
    on ehr.encounter_diagnosis (encounter_id) where is_primary;

create table ehr.medication_order (
    medication_order_id bigint primary key,
    patient_id integer not null references ehr.patient,
    -- Empty for repeat prescriptions, which are issued without a visit.
    encounter_id bigint,
    atc_code text not null references ehr.atc_code,
    dose numeric not null check (dose > 0),
    dose_unit text not null,
    frequency text not null,
    start_date date not null,
    stop_date date not null check (stop_date >= start_date),
    -- If there is an encounter, it is this patient's. (With encounter_id
    -- empty, a two-column foreign key is not checked: MATCH SIMPLE.)
    foreign key (encounter_id, patient_id) references ehr.encounter (encounter_id, patient_id)
);

create table ehr.lab_order (
    lab_order_id bigint primary key,
    patient_id integer not null references ehr.patient,
    -- Empty for follow-up and monitoring tests outside a visit.
    encounter_id bigint,
    loinc_code text not null references ehr.loinc_code,
    ordered_at timestamp not null,
    foreign key (encounter_id, patient_id) references ehr.encounter (encounter_id, patient_id)
);

create table ehr.lab_result (
    -- One result per order, so the order's key is the result's key too.
    lab_order_id bigint primary key references ehr.lab_order,
    value numeric not null,
    unit text not null,
    reference_low numeric,
    reference_high numeric,
    resulted_at timestamp not null,
    check (reference_low < reference_high)
);
