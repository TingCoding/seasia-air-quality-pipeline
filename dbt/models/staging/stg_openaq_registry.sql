-- The pinned station registry, as committed to the repository.
--
-- Timestamps arrive as text because the seed's column types are declared
-- rather than inferred. Casting them is therefore this model's job.
--
-- The cast is guarded rather than direct. This file is deliberately editable
-- by hand, so a cell may hold an empty string, a stray space, or a date a
-- spreadsheet rewrote on save. A bare `::timestamptz` fails the whole build on
-- any of those. Checking the shape first turns an unparseable value into NULL,
-- which the tests can then report, instead of a crash that stops everything.
--
-- The columns are also cast to text first, so the model works whether the
-- seed loaded them as text or as real timestamps.

with seed as (

    select * from {{ ref('openaq_stations') }}

),

trimmed as (

    select
        station_id,
        location_key,
        station_name,
        provider                            as provider_name,
        owner                               as owner_name,
        is_monitor                          as is_reference_monitor,
        latitude,
        longitude,
        timezone,
        -- Cast to text before anything else. Whether these columns arrive as
        -- text or as timestamps depends on the seed's configured types, and a
        -- model should not break when that changes. Normalising to text first
        -- makes the parsing below behave the same either way.
        trim(coalesce(first_seen_at::text, ''))   as first_seen_text,
        trim(coalesce(last_seen_at::text, ''))    as last_seen_text,
        trim(coalesce(selected_on::text, ''))     as selected_on_text
    from seed

),

parsed as (

    select
        *,
        case
            when first_seen_text ~ '^\d{4}-\d{2}-\d{2}'
            then first_seen_text::timestamptz
        end                                 as first_seen_at,
        case
            when last_seen_text ~ '^\d{4}-\d{2}-\d{2}'
            then last_seen_text::timestamptz
        end                                 as last_seen_at_at_selection,
        case
            when selected_on_text ~ '^\d{4}-\d{2}-\d{2}$'
            then selected_on_text::date
        end                                 as selected_on
    from trimmed

)

select
    station_id,
    location_key,
    station_name,
    provider_name,
    owner_name,
    is_reference_monitor,
    latitude,
    longitude,
    timezone,
    first_seen_at,
    last_seen_at_at_selection,
    selected_on,

    -- Surfaces a malformed cell rather than letting it become NULL with no
    -- trace of what was there.
    (first_seen_text  <> '' and first_seen_at is null)
    or (last_seen_text   <> '' and last_seen_at_at_selection is null)
    or (selected_on_text <> '' and selected_on is null)
                                            as has_unparseable_dates
from parsed
