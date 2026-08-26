-- Relative humidity must fall between 0 and 100 percent.

select
    measurement_key,
    location_key,
    observed_at,
    measurement_value
from {{ ref('fct_hourly_measurement') }}
where variable_name = 'relative_humidity_2m'
  and measurement_value is not null
  and (measurement_value < 0 or measurement_value > 100)
