-- Hourly station measurements, cleaned and renamed.
--
-- OpenAQ names the fine particulate parameter `pm25`; Open-Meteo calls the
-- same thing `pm2_5`. The two are reconciled here, explicitly, so that a join
-- between a modelled and a measured value cannot fail silently on a naming
-- difference.

with source as (
    select * from {{ source('raw', 'openaq_measurements') }}
),

renamed as (
    select
        sensor_id,
        station_id,
        location_key,
        observed_at::timestamptz            as observed_at,

        case parameter
            when 'pm25' then 'pm2_5'
            else parameter
        end                                 as variable_name,

        parameter                           as source_parameter_name,
        value::double precision             as measurement_value,
        unit                                as measurement_unit,
        coverage_pct,
        source                              as source_system,
        ingested_at
    from source
)

select * from renamed
