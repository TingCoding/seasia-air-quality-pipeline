-- Station dimension.
--
-- Combines what was selected (the committed registry) with what the API
-- reports now. Keeping both lets a reader answer a question that would
-- otherwise need an investigation: has a station gone quiet since we chose it?
--
-- Providers are not equivalent. A government reference monitor and a low-cost
-- community sensor both appear in OpenAQ under the same schema, but they do
-- not carry the same weight. The distinction is surfaced rather than resolved,
-- because how much to trust each one is the analyst's call, not the
-- pipeline's.

with registry as (
    select * from {{ ref('stg_openaq_registry') }}
),

reported as (
    select * from {{ ref('stg_openaq_stations') }}
),

joined as (
    select
        r.station_id,
        r.location_key,
        coalesce(rep.station_name, r.station_name)          as station_name,
        coalesce(rep.provider_name, r.provider_name)        as provider_name,
        coalesce(rep.owner_name, r.owner_name)              as owner_name,
        coalesce(rep.is_reference_monitor,
                 r.is_reference_monitor, false)             as is_reference_monitor,
        coalesce(rep.latitude, r.latitude)                  as latitude,
        coalesce(rep.longitude, r.longitude)                as longitude,
        coalesce(rep.timezone, r.timezone)                  as timezone,
        rep.distance_metres,
        r.selected_on,
        r.last_seen_at_at_selection,
        rep.last_seen_at                                    as last_seen_at,
        (rep.station_id is null)                            as missing_from_api
    from registry r
    left join reported rep on rep.station_id = r.station_id
)

select
    *,
    case
        when provider_name in ('Air4Thai', 'AirNow', 'Hanoi Air Quality')
             or is_reference_monitor then 'reference'
        else 'low_cost'
    end                                                     as station_class,

    -- Days between the station being chosen and its most recent reading. A
    -- large gap means the registry is describing a station that has since
    -- fallen silent.
    case
        when last_seen_at is null then null
        else (last_seen_at::date - selected_on)
    end                                                     as days_since_selection
from joined
