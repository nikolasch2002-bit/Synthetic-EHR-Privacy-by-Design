-- Grain: one row per drug-lab rule: lab results inside an exposure window,
-- how many broke the rule, and the rate. Counts suppressed below k; the rate
-- only when both its counts are published.
with counts as (
    select
        rule,
        count(*) as results,
        count(*) filter (where rule_triggered) as events
    from {{ ref('fact_drug_lab_event') }}
    group by rule
)

select
    rule,
    {{ suppress('results') }} as results,
    {{ suppress('events') }} as events,
    {{ suppressed_rate('events', 'results') }} as rate_pct,
    {{ is_suppressed('results') }} or {{ is_suppressed('events') }} as is_suppressed
from counts
