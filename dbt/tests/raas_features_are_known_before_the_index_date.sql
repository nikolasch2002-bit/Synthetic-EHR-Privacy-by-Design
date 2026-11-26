-- The leakage test (spec, "Prediction model", step 1): every feature taken
-- from a lab result must come from before the index date, within 365 days.
-- Returns a row for each start that breaks it.
select raas_start_key, index_date, egfr_before_date, potassium_before_date
from {{ ref('fact_raas_start') }}
where
    egfr_before_date >= index_date
    or egfr_before_date < index_date - 365
    or potassium_before_date >= index_date
    or potassium_before_date < index_date - 365
