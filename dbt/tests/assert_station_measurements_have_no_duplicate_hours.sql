-- One sensor may report a given hour only once.
--
-- The raw primary key already enforces this. The test exists because a primary
-- key protects the table it sits on, not the models built from it, and a join
-- introduced later could quietly fan the rows out.

select
    sensor_id,
    observed_at,
    count(*) as occurrences
from {{ ref('fct_station_measurement') }}
group by sensor_id, observed_at
having count(*) > 1
