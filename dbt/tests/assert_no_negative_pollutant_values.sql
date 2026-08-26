-- Pollutant concentrations cannot be negative.
-- A negative value points to sensor calibration faults or a parsing error.

select
    measurement_key,
    location_key,
    observed_at,
    variable_name,
    measurement_value
from {{ ref('fct_hourly_measurement') }}
where measurement_domain = 'air_quality'
  and measurement_value < 0
