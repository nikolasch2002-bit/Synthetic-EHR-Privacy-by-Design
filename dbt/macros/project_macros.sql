{# The six conditions, as named in the generator's config and in dim_diagnosis.
   A singular test (tests/conditions_match_reference.sql) checks the two agree. #}
{% macro conditions() -%}
    {{ return(['hypertension', 'hyperlipidaemia', 'type2_diabetes', 'ckd', 'atrial_fibrillation', 'heart_failure']) }}
{%- endmacro %}

{# Ten-year age bands from 18, with 90+. The argument is wrapped in
   parentheses: a pasted expression like "a - b" must not lose its order. #}
{% macro age_band(age) -%}
    case
        when ({{ age }}) >= 90 then '90+'
        when ({{ age }}) >= 30
            then (floor(({{ age }}) / 10) * 10)::int || '-' || (floor(({{ age }}) / 10) * 10 + 9)::int
        else '18-29'
    end
{%- endmacro %}

{# A yyyymmdd integer key from a date or timestamp, to join dim_date. #}
{% macro date_key(value) -%}
    to_char(({{ value }}), 'YYYYMMDD')::int
{%- endmacro %}
