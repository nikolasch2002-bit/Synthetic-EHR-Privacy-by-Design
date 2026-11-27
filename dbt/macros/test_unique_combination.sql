{# A generic test: the combination of `columns` is unique in the model.
   Fails with one row per repeated combination. #}
{% test unique_combination(model, columns) %}
    select {{ columns | join(', ') }}, count(*) as rows_with_it
    from {{ model }}
    group by {{ columns | join(', ') }}
    having count(*) > 1
{% endtest %}
