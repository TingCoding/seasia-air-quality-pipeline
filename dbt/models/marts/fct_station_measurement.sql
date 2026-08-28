-- Measured hourly values from physical monitoring stations.
--
-- Deliberately separate from fct_hourly_measurement, which holds modelled
-- values at a coordinate. A modelled figure and a measured one answer
-- different questions and carry different uncertainty; merging them into one
-- fact table would let a reader treat them as interchangeable, which they are
-- not.

with measurements as (
    select * from {{ ref('stg_openaq_measurements') }}
),

stations as (
    select station_id, timezone, station_class, provider_name
    from {{ ref('dim_station') }}
)

select
    md5(m.sensor_id::text || '|' || m.observed_at::text)    as station_measurement_key,
    m.sensor_id,
    m.station_id,
    m.location_key,
    m.observed_at,
    (m.observed_at at time zone coalesce(s.timezone, 'UTC'))
                                                            as observed_at_local,
    m.observed_at::date                                     as date_day,
    extract(hour from m.observed_at)::int                   as hour_utc,
    m.variable_name,
    m.measurement_value,
    m.measurement_unit,
    m.coverage_pct,
    s.station_class,
    s.provider_name,
    m.source_system,
    m.ingested_at
from measurements m
left join stations s on s.station_id = m.station_id
