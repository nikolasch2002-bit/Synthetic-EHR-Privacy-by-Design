{#
    Use the schema named in the config as it is ("marts"), instead of dbt's
    default of prefixing it with the target schema ("marts_marts").
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ (custom_schema_name or target.schema) | trim }}
{%- endmacro %}
