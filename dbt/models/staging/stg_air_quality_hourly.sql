-- Same as stg_weather_hourly, for the air quality domain.

with source as (
    select * from {{ source('raw', 'air_quality_hourly') }}
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
        'air_quality'                         as measurement_domain
    from source
)

select * from renamed
