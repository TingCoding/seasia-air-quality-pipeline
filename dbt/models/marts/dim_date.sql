-- Date dimension, built from the range of data actually present.

with bounds as (
    select
        min(observed_at)::date as start_date,
        max(observed_at)::date as end_date
    from {{ ref('int_measurements_unioned') }}
),

spine as (
    select generate_series(start_date, end_date, interval '1 day')::date as date_day
    from bounds
)

select
    date_day,
    extract(year    from date_day)::int  as year,
    extract(quarter from date_day)::int  as quarter,
    extract(month   from date_day)::int  as month,
    to_char(date_day, 'Month')           as month_name,
    extract(day     from date_day)::int  as day_of_month,
    extract(isodow  from date_day)::int  as day_of_week,
    to_char(date_day, 'Day')             as day_name,
    extract(isodow from date_day) in (6, 7) as is_weekend
from spine
