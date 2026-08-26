-- Cleans raw weather data: consistent naming, explicit casts, and a domain tag
-- so downstream layers can filter without knowing the source table.

with source as (
    select * from {{ source('raw', 'weather_hourly') }}
),

renamed as (
    select
        location_key,
        observed_at::timestamptz              as observed_at,
        variable                              as variable_name,
        value::double precision               as measurement_value,
        unit                                  as measurement_unit,
        source                                as source_system,
        ingested_at,
        'weather'                             as measurement_domain
    from source
)

select * from renamed
