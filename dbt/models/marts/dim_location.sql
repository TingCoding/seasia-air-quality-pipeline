-- Dimensi lokasi, bersumber dari seed agar metadata kota (nama, negara,
-- zona waktu) tidak tergantung pada data yang masuk dari API.

with seed as (
    select * from {{ ref('locations') }}
),

observed as (
    select distinct location_key
    from {{ ref('int_measurements_unioned') }}
)

select
    s.location_key,
    s.city,
    s.country_code,
    s.country,
    s.latitude,
    s.longitude,
    s.timezone,
    (o.location_key is not null) as has_measurements
from seed s
left join observed o on o.location_key = s.location_key
