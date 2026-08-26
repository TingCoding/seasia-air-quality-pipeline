-- Tabel fakta. Satu baris mewakili satu pengukuran:
-- lokasi x waktu x variabel x sumber.
--
-- Waktu lokal dihitung di sini, bukan disimpan sejak lapisan raw, agar
-- lapisan mentah tetap netral terhadap zona waktu.

with measurements as (
    select * from {{ ref('int_measurements_unioned') }}
),

locations as (
    select location_key, timezone from {{ ref('dim_location') }}
)

select
    m.measurement_key,
    m.location_key,
    m.observed_at,
    (m.observed_at at time zone l.timezone)     as observed_at_local,
    m.observed_at::date                          as date_day,
    extract(hour from m.observed_at)::int        as hour_utc,
    m.variable_name,
    m.measurement_domain,
    m.measurement_value,
    m.measurement_unit,
    m.source_system,
    (m.measurement_value is null)                as is_missing,
    m.ingested_at
from measurements m
left join locations l on l.location_key = m.location_key
