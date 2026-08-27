-- Rejects values that are physically impossible for the variable in question.
--
-- These bounds are deliberately generous. The aim is to catch unit errors,
-- parsing mistakes and broken sensors, not to second-guess unusual weather.
-- Relative humidity is covered separately by assert_humidity_within_range.

with bounds as (

    select * from (
        values
            ('temperature_2m',       -50.0,   60.0),
            ('precipitation',          0.0,  500.0),
            ('wind_speed_10m',         0.0,  300.0),
            ('wind_direction_10m',     0.0,  360.0),
            ('pm10',                   0.0, 2000.0),
            ('pm2_5',                  0.0, 2000.0),
            ('carbon_monoxide',        0.0, 50000.0),
            ('nitrogen_dioxide',       0.0, 1000.0),
            ('ozone',                  0.0, 1000.0)
    ) as t (variable_name, min_allowed, max_allowed)

)

select
    f.measurement_key,
    f.location_key,
    f.observed_at,
    f.variable_name,
    f.measurement_value,
    b.min_allowed,
    b.max_allowed
from {{ ref('fct_hourly_measurement') }} f
join bounds b on b.variable_name = f.variable_name
where f.measurement_value is not null
  and (f.measurement_value < b.min_allowed
       or f.measurement_value > b.max_allowed)
