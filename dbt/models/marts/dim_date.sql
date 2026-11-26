-- Grain: one row per calendar day, from before the earliest possible onset
-- (15 years before the history) to a year after it.
select
    {{ date_key('d') }} as date_key,
    d::date as calendar_date,
    extract(year from d)::int as year,
    extract(month from d)::int as month,
    extract(isodow from d)::int as weekday
from generate_series(date '2000-01-01', date '2026-12-31', interval '1 day') as d
