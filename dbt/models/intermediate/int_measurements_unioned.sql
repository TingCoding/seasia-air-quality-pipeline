-- Menggabungkan kedua domain menjadi satu aliran.
--
-- Keputusan: cuaca dan kualitas udara disatukan dalam bentuk panjang
-- (satu baris per variabel), bukan dilebarkan menjadi satu kolom per
-- variabel. Alasannya, daftar variabel bisa bertambah tanpa mengubah
-- struktur tabel, dan penambahan sumber baru tidak memaksa migrasi skema.

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
