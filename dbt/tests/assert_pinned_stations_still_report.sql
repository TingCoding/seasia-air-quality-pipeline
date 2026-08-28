{{ config(severity='warn') }}

-- Flags stations that were selected for ingestion but have since fallen silent.
--
-- Severity is 'warn': a station going quiet is news about the world, not a
-- defect in this pipeline. It should reach whoever maintains the registry
-- without failing a build.

select
    station_id,
    location_key,
    station_name,
    provider_name,
    selected_on,
    last_seen_at,
    missing_from_api
from {{ ref('dim_station') }}
where missing_from_api
   or last_seen_at is null
   or last_seen_at < (current_date - interval '90 days')
