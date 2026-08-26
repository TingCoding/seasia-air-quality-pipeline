-- Membersihkan data cuaca mentah: penamaan diseragamkan, tipe dipastikan,
-- dan kategori variabel ditambahkan agar mudah disaring di lapisan berikutnya.

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
