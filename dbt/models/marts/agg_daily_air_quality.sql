-- Ringkasan harian polutan per kota.
--
-- Kolom measurement_completeness_pct sengaja disertakan agar pengguna data
-- tahu seberapa lengkap dasar perhitungan rata-rata harian ini. Rata-rata
-- dari 3 jam data tidak setara dengan rata-rata dari 24 jam, dan perbedaan
-- itu harus terlihat, bukan disembunyikan.

with facts as (
    select *
    from {{ ref('fct_hourly_measurement') }}
    where measurement_domain = 'air_quality'
)

select
    location_key,
    date_day,
    variable_name,
    measurement_unit,
    round(avg(measurement_value)::numeric, 2)  as avg_value,
    round(min(measurement_value)::numeric, 2)  as min_value,
    round(max(measurement_value)::numeric, 2)  as max_value,
    count(*)                                    as expected_hours,
    count(measurement_value)                    as observed_hours,
    round(100.0 * count(measurement_value) / nullif(count(*), 0), 1)
                                                as measurement_completeness_pct
from facts
group by location_key, date_day, variable_name, measurement_unit
