-- A small, deterministic dataset for continuous integration.
--
-- Building the models against an empty database only proves the SQL parses.
-- Feeding known rows through proves it produces the right answer, and lets the
-- data quality tests do real work on every push.
--
-- The fixture is deliberately awkward: it includes a NULL modelled hour, a
-- station hour that is simply absent rather than NULL, and two sensors at one
-- station reporting the same parameter -- the three shapes that caused real
-- problems during development.

-- ---------------------------------------------------------------- modelled

INSERT INTO raw.weather_hourly
    (location_key, observed_at, variable, value, unit, source)
SELECT
    'bangkok',
    generate_series(
        timestamptz '2025-01-01 00:00:00+00',
        timestamptz '2025-01-01 23:00:00+00',
        interval '1 hour'
    ),
    'temperature_2m',
    28.5,
    '°C',
    'open-meteo-archive'
ON CONFLICT DO NOTHING;

INSERT INTO raw.air_quality_hourly
    (location_key, observed_at, variable, value, unit, source)
SELECT
    'bangkok',
    hour_ts,
    'pm2_5',
    -- one hour deliberately has no value, as Open-Meteo reports gaps
    CASE WHEN extract(hour from hour_ts) = 5 THEN NULL ELSE 20.0 END,
    'µg/m³',
    'open-meteo-air-quality'
FROM generate_series(
    timestamptz '2025-01-01 00:00:00+00',
    timestamptz '2025-01-01 23:00:00+00',
    interval '1 hour'
) AS hour_ts
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------- measured

INSERT INTO raw.openaq_stations
    (station_id, location_key, station_name, provider, owner,
     is_monitor, is_mobile, latitude, longitude, timezone, distance_metres,
     first_seen_at, last_seen_at)
VALUES
    (701, 'bangkok', 'Sukhothai Thammathirat', 'Air4Thai', 'Gov',
     true, false, 13.907861, 100.535641, 'Asia/Bangkok', 1200.0,
     '2016-01-30T02:00:00Z', '2026-08-28T07:00:00Z')
ON CONFLICT (station_id) DO NOTHING;

-- two sensors, same parameter, same station: the duplication that must not be
-- silently collapsed
INSERT INTO raw.openaq_sensors (sensor_id, station_id, parameter, unit)
VALUES
    (9001, 701, 'pm25', 'µg/m³'),
    (9002, 701, 'pm25', 'µg/m³')
ON CONFLICT (sensor_id) DO NOTHING;

INSERT INTO raw.openaq_measurements
    (sensor_id, station_id, location_key, observed_at, parameter,
     value, unit, coverage_pct, source)
SELECT
    9001, 701, 'bangkok', hour_ts, 'pm25', 24.0, 'µg/m³', 100.0, 'openaq'
FROM generate_series(
    timestamptz '2025-01-01 00:00:00+00',
    timestamptz '2025-01-01 23:00:00+00',
    interval '1 hour'
) AS hour_ts
-- hours 10 and 11 are omitted entirely: OpenAQ drops the row rather than
-- returning NULL, and the coverage model must notice
WHERE extract(hour from hour_ts) NOT IN (10, 11)
ON CONFLICT DO NOTHING;

INSERT INTO raw.openaq_measurements
    (sensor_id, station_id, location_key, observed_at, parameter,
     value, unit, coverage_pct, source)
SELECT
    9002, 701, 'bangkok', hour_ts, 'pm25', 26.0, 'µg/m³', 100.0, 'openaq'
FROM generate_series(
    timestamptz '2025-01-01 00:00:00+00',
    timestamptz '2025-01-01 23:00:00+00',
    interval '1 hour'
) AS hour_ts
ON CONFLICT DO NOTHING;
