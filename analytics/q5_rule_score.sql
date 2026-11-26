-- Question 5, first part: how well does the rule baseline score separate
-- RAAS-inhibitor starts with and without hyperkalaemia? (The model comes in
-- week 6.) Only starts with potassium measured in the 30 days count: not
-- measured is not the same as normal. Those left out are counted in the last row.
select
    rule_score::text as rule_score,
    count(*) as starts,
    count(*) filter (where hyperkalaemia) as events,
    round(100.0 * count(*) filter (where hyperkalaemia) / count(*), 1) as event_rate_pct
from marts.fact_raas_start
where potassium_measured
group by rule_score

union all

select 'not measured (left out)', count(*), null, null
from marts.fact_raas_start
where not potassium_measured

order by rule_score
