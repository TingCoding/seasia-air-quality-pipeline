-- Setiap kombinasi lokasi, waktu, variabel, dan sumber harus muncul sekali saja.
-- Uji ini adalah jaring pengaman terhadap kegagalan idempotensi di ingestion.

select
    location_key,
    observed_at,
    variable_name,
    source_system,
    count(*) as jumlah
from {{ ref('fct_hourly_measurement') }}
group by location_key, observed_at, variable_name, source_system
having count(*) > 1
