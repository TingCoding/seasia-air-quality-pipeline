-- Konsentrasi polutan tidak mungkin negatif.
-- Nilai negatif menandakan kesalahan kalibrasi sensor atau kesalahan penguraian.

select
    measurement_key,
    location_key,
    observed_at,
    variable_name,
    measurement_value
from {{ ref('fct_hourly_measurement') }}
where measurement_domain = 'air_quality'
  and measurement_value < 0
