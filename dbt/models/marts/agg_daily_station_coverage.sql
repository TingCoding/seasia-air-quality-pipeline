-- Daily reporting completeness per station and parameter.
--
-- OpenAQ expresses a missing hour differently from Open-Meteo: the row is
-- simply absent, not present with a NULL. A NULL-based check therefore finds
-- nothing here, and a dead sensor would pass every test while reporting no
-- data at all.
--
-- Completeness is measured instead against what a full day should contain --
-- 24 hourly values -- so silence becomes visible.

with measured as (

    select
        location_key,
        station_id,
        variable_name,
        date_day,
        count(distinct observed_at)                 as observed_hours,
        avg(coverage_pct)                           as avg_source_coverage_pct
    from {{ ref('fct_station_measurement') }}
    where measurement_value is not null
    group by location_key, station_id, variable_name, date_day

)

select
    location_key,
    station_id,
    variable_name,
    date_day,
    observed_hours,
    24                                              as expected_hours,
    round(100.0 * observed_hours / 24, 1)           as reporting_completeness_pct,
    round(avg_source_coverage_pct::numeric, 1)      as avg_source_coverage_pct,
    (observed_hours < 24)                           as has_missing_hours
from measured
