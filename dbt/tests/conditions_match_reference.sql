-- The conditions() macro names exactly the conditions in dim_diagnosis
-- (written from the generator's config). Returns a row for each mismatch.
with macro_list as (
    select unnest(array[{% for c in conditions() %}'{{ c }}'{% if not loop.last %}, {% endif %}{% endfor %}]) as condition
)

select condition from macro_list
where condition not in (select condition from {{ ref('dim_diagnosis') }})
union all
select condition from {{ ref('dim_diagnosis') }}
where condition not in (select condition from macro_list)
