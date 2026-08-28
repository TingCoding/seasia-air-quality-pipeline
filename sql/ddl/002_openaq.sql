-- OpenAQ raw tables.
--
-- Kept separate from the Open-Meteo tables rather than forced into a shared
-- shape. OpenAQ data is measured at identifiable physical stations, each with
-- its own operator, instrument and lifespan. Flattening that away at the raw
-- layer would discard the very metadata that makes the source worth having.

CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.openaq_stations (
    station_id      BIGINT      NOT NULL,
    location_key    TEXT        NOT NULL,
    station_name    TEXT,
    provider        TEXT,
    owner           TEXT,
    is_monitor      BOOLEAN,
    is_mobile       BOOLEAN,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    timezone        TEXT,
    distance_metres DOUBLE PRECISION,
    first_seen_at   TIMESTAMPTZ,
    last_seen_at    TIMESTAMPTZ,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (station_id)
);

CREATE TABLE IF NOT EXISTS raw.openaq_sensors (
    sensor_id       BIGINT      NOT NULL,
    station_id      BIGINT      NOT NULL,
    parameter       TEXT        NOT NULL,
    unit            TEXT,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (sensor_id)
);

CREATE TABLE IF NOT EXISTS raw.openaq_measurements (
    sensor_id       BIGINT      NOT NULL,
    station_id      BIGINT      NOT NULL,
    location_key    TEXT        NOT NULL,
    observed_at     TIMESTAMPTZ NOT NULL,
    parameter       TEXT        NOT NULL,
    value           DOUBLE PRECISION,
    unit            TEXT,
    -- OpenAQ reports how complete each hourly average is. A mean built from
    -- four readings is not the same as one built from sixty, so the figure is
    -- carried through rather than discarded.
    coverage_pct    DOUBLE PRECISION,
    source          TEXT        NOT NULL DEFAULT 'openaq',
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (sensor_id, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_openaq_meas_observed_at
    ON raw.openaq_measurements (observed_at);
CREATE INDEX IF NOT EXISTS idx_openaq_meas_location
    ON raw.openaq_measurements (location_key, parameter, observed_at);
CREATE INDEX IF NOT EXISTS idx_openaq_stations_location
    ON raw.openaq_stations (location_key);
