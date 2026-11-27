-- Grain: one row per rule score (0 to 5): RAAS-inhibitor starts with
-- potassium measured, how many had hyperkalaemia, and the rate. Suppressed
-- below k.
with counts as (
    select
        rule_score,
        count(*) as starts,
        count(*) filter (where hyperkalaemia) as events
    from {{ ref('fact_raas_start') }}
    where potassium_measured
    group by rule_score
)

select
    rule_score,
    {{ suppress('starts') }} as starts,
    {{ suppress('events') }} as events,
    {{ suppressed_rate('events', 'starts') }} as event_rate_pct,
    {{ is_suppressed('starts') }} or {{ is_suppressed('events') }} as is_suppressed
from counts
