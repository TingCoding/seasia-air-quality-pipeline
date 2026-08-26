-- Each location, hour, variable and source combination must appear exactly once.
-- This test is the safety net against a regression in ingestion idempotency.

select
    location_key,
    observed_at,
    variable_name,
    source_system,
    count(*) as occurrences
from {{ ref('fct_hourly_measurement') }}
group by location_key, observed_at, variable_name, source_system
having count(*) > 1
