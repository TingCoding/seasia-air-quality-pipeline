-- Station metadata as currently reported by the API.
--
-- Read alongside stg_openaq_registry: one says what the API reports today, the
-- other says what this pipeline chose to ingest and when. Divergence between
-- them is the signal that a station has gone quiet since it was selected.

with source as (
    select * from {{ source('raw', 'openaq_stations') }}
)

select
    station_id,
    location_key,
    station_name,
    provider                                as provider_name,
    owner                                   as owner_name,
    coalesce(is_monitor, false)             as is_reference_monitor,
    coalesce(is_mobile, false)              as is_mobile,
    latitude,
    longitude,
    timezone,
    distance_metres,
    first_seen_at,
    last_seen_at,
    ingested_at
from source
