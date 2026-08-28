-- Modelled PM2.5 against measured PM2.5, per city per day.
--
-- This is the question the second source was added to answer: how closely does
-- a reanalysis model track what instruments on the ground actually record?
--
-- Two details matter for the comparison to be honest.
--
-- First, duplicate sensors. A station may expose two PM2.5 sensors, so values
-- are averaged within a station before averaging across stations. Skipping
-- that step would silently weight such stations twice.
--
-- Second, completeness. Both sides carry the number of hours behind their
-- average. A day where the model has 24 hours and the stations have 3 is not a
-- like-for-like comparison, and the reader is given what they need to exclude
-- it rather than being quietly handed a misleading number.

with modelled as (

    select
        location_key,
        date_day,
        avg(measurement_value)              as modelled_pm25,
        count(measurement_value)            as modelled_hours
    from {{ ref('fct_hourly_measurement') }}
    where variable_name = 'pm2_5'
      and measurement_value is not null
    group by location_key, date_day

),

per_station as (

    -- collapse duplicate sensors within a station first
    select
        location_key,
        station_id,
        date_day,
        avg(measurement_value)              as station_pm25,
        count(distinct observed_at)         as station_hours
    from {{ ref('fct_station_measurement') }}
    where variable_name = 'pm2_5'
      and measurement_value is not null
    group by location_key, station_id, date_day

),

measured as (

    select
        location_key,
        date_day,
        avg(station_pm25)                   as measured_pm25,
        count(distinct station_id)          as station_count,
        max(station_hours)                  as measured_hours
    from per_station
    group by location_key, date_day

)

select
    coalesce(mo.location_key, me.location_key)              as location_key,
    coalesce(mo.date_day, me.date_day)                      as date_day,

    round(mo.modelled_pm25::numeric, 2)                     as modelled_pm25,
    round(me.measured_pm25::numeric, 2)                     as measured_pm25,

    round((me.measured_pm25 - mo.modelled_pm25)::numeric, 2) as difference,
    case
        when mo.modelled_pm25 is null or mo.modelled_pm25 = 0 then null
        else round((me.measured_pm25 / mo.modelled_pm25)::numeric, 3)
    end                                                     as measured_over_modelled,

    mo.modelled_hours,
    me.measured_hours,
    me.station_count,

    -- Only days where both sides rest on a near-complete day should be used
    -- for headline comparisons.
    (mo.modelled_hours >= 20 and me.measured_hours >= 20)   as is_comparable

from modelled mo
full outer join measured me
    on me.location_key = mo.location_key
   and me.date_day = mo.date_day
