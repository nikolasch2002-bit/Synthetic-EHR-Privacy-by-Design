{# Grants for one dbt-built table, run in its post_hook: the readers may
   select from it; etl, which writes, gets full access. Nothing else is
   granted, so every other role is refused. #}
{% macro grant_read(relation, readers) -%}
    grant select on {{ relation }} to {{ readers | join(', ') }};
    grant select, insert, update, delete on {{ relation }} to etl
{%- endmacro %}

{# The schemas and who may use them, once, before any model runs (on-run-start).
   Not in each table's post_hook: dbt builds tables in parallel threads, and
   Postgres refuses two grants on one schema at the same moment ("tuple
   concurrently updated"). #}
{% macro create_schemas_with_usage() -%}
    create schema if not exists marts;
    create schema if not exists marts_public;
    grant usage on schema marts to researcher, data_steward, etl;
    grant usage on schema marts_public to public_app, researcher, data_steward, etl
{%- endmacro %}
