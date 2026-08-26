-- Location dimension, sourced from a seed so that city metadata (name,
-- country, timezone) does not depend on whatever the API happens to return.

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
