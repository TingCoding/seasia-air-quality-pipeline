{{ config(severity='warn') }}

-- Flags days where a city reports fewer hours than a full day should contain.
--
-- Partial days are not necessarily wrong -- the first and last day of a load
-- window are legitimately incomplete. This test exists to make sure such days
-- are noticed rather than silently averaged into a trend.
--
-- Severity is 'warn' for the same reason: incomplete days are worth knowing
-- about, but the first and last day of any load window are legitimately partial.

select
    location_key,
    date_day,
    variable_name,
    observed_hours,
    expected_hours,
    measurement_completeness_pct
from {{ ref('agg_daily_air_quality') }}
where measurement_completeness_pct < 75
