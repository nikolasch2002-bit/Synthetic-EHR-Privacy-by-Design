-- Grain: one row per department.
select
    department_id,
    code,
    name
from {{ source('ehr', 'department') }}
