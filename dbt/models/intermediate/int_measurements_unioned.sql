-- Unions both domains into a single stream.
--
-- Decision: weather and air quality are combined in long format (one row per
-- variable) rather than pivoted into one column per variable. The list of
-- variables will grow over time, and long format absorbs that without a
-- schema migration.

with weather as (
    select * from {{ ref('stg_weather_hourly') }}
),

air_quality as (
    select * from {{ ref('stg_air_quality_hourly') }}
),

unioned as (
    select * from weather
    union all
    select * from air_quality
)

select
    md5(
        location_key || '|' ||
        observed_at::text || '|' ||
        variable_name || '|' ||
        source_system
    )                                   as measurement_key,
    location_key,
    observed_at,
    variable_name,
    measurement_domain,
    measurement_value,
    measurement_unit,
    source_system,
    ingested_at
from unioned
