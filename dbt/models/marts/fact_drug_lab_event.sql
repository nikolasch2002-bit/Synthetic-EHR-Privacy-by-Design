-- Grain: one row per lab result that falls inside an exposure period of a
-- medicine linked to that test by a rule (dim_drug_lab_rule), and, for a rule
-- about starts, within the rule's window after the start. A result can
-- appear once per rule it belongs to.
with rule_drug as (
    select
        r.*,
        d.atc_code
    from {{ ref('dim_drug_lab_rule') }} as r
    inner join {{ ref('dim_drug') }} as d using (drug_class)
),

matched as (
    -- A result can fall in two periods of one rule (a loop diuretic and a
    -- thiazide at once): keep one row per result and rule, the period that
    -- started most recently, with atc_code breaking ties.
    select distinct on (l.lab_result_key, r.rule)
        l.lab_result_key,
        l.pseudonym,
        r.rule,
        r.atc_code,
        l.loinc_code,
        l.date_key,
        l.ordered_at,
        l.value,
        l.ordered_at::date - e.start_date as days_since_start,
        -- The threshold, as a value: for ALT it is a multiple of the upper limit.
        case
            when r.threshold_times_upper_limit then r.threshold * l.reference_high
            else r.threshold
        end as threshold_value,
        r.comparison
    from {{ ref('fact_lab_result') }} as l
    inner join {{ ref('dim_lab_test') }} as t using (loinc_code)
    inner join rule_drug as r on r.test_name = t.test_name
    inner join {{ ref('fact_medication_exposure') }} as e
        on e.pseudonym = l.pseudonym
        and e.atc_code = r.atc_code
        and l.ordered_at::date between e.start_date and e.stop_date
    where
        r.window_days_after_start is null
        or (
            -- A rule about starts: only periods that begin far enough into
            -- the history to be a start (180 days without the medicine
            -- before them are in the data), and only tests in the window.
            e.start_date >= date '{{ var("history_start") }}' + 180
            and l.ordered_at::date - e.start_date between 1 and r.window_days_after_start
        )
    order by l.lab_result_key, r.rule, e.start_date desc, r.atc_code
)

select
    row_number() over (order by pseudonym, ordered_at, rule, lab_result_key) as event_key,
    lab_result_key,
    pseudonym,
    rule,
    atc_code,
    loinc_code,
    date_key,
    ordered_at,
    value,
    days_since_start,
    case comparison
        when '>=' then value >= threshold_value
        when '>' then value > threshold_value
        when '<' then value < threshold_value
    end as rule_triggered
from matched
