{{ config(severity='warn') }}

-- Detects stretches where a series stops reporting for more than 24 hours.
--
-- A dead sensor rarely announces itself. Row counts stay plausible and averages
-- still compute -- the series simply stops moving. Comparing each observation
-- against the previous one surfaces the silence.
--
-- Severity is 'warn': a gap usually reflects the upstream source rather than a
-- defect in this pipeline. It must be visible, but it should not block a build.

with observed as (

    select
        location_key,
        variable_name,
        observed_at,
        lag(observed_at) over (
            partition by location_key, variable_name
            order by observed_at
        ) as previous_observed_at

    from {{ ref('fct_hourly_measurement') }}
    where measurement_value is not null

)

select
    location_key,
    variable_name,
    previous_observed_at                                            as gap_start,
    observed_at                                                     as gap_end,
    round(extract(epoch from (observed_at - previous_observed_at)) / 3600.0, 1)
                                                                    as gap_hours
from observed
where previous_observed_at is not null
  and observed_at - previous_observed_at > interval '24 hours'
