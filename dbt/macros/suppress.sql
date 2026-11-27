{# Small-cell suppression: a count below k becomes null (suppressed). Zero
   is suppressed too: "no one" can be as telling as "one". The argument is
   wrapped in parentheses, so a pasted expression keeps its order. #}
{% macro suppress(count) -%}
    case when ({{ count }}) < {{ var('suppression_k') }} then null else ({{ count }}) end
{%- endmacro %}

{# True where suppress() hid the count, so a reader can tell "hidden" from "none". #}
{% macro is_suppressed(count) -%}
    (({{ count }}) < {{ var('suppression_k') }})
{%- endmacro %}

{# A rate published only when both its counts are: otherwise it gives the hidden count away. #}
{% macro suppressed_rate(events, total) -%}
    case
        when ({{ events }}) < {{ var('suppression_k') }} or ({{ total }}) < {{ var('suppression_k') }} then null
        else round(100.0 * ({{ events }}) / ({{ total }}), 1)
    end
{%- endmacro %}
