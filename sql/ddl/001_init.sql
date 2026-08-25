-- Dijalankan otomatis saat container PostgreSQL pertama kali dibuat.
-- Lapisan raw menyimpan respons API apa adanya, tanpa transformasi.

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS raw.weather_hourly (
    location_key   TEXT        NOT NULL,
    observed_at    TIMESTAMPTZ NOT NULL,
    variable       TEXT        NOT NULL,
    value          DOUBLE PRECISION,
    unit           TEXT,
    source         TEXT        NOT NULL DEFAULT 'open-meteo',
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (location_key, observed_at, variable, source)
);

CREATE TABLE IF NOT EXISTS raw.air_quality_hourly (
    location_key   TEXT        NOT NULL,
    observed_at    TIMESTAMPTZ NOT NULL,
    variable       TEXT        NOT NULL,
    value          DOUBLE PRECISION,
    unit           TEXT,
    source         TEXT        NOT NULL,
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (location_key, observed_at, variable, source)
);

-- Catatan hasil pemeriksaan kualitas data (dipakai mulai Tahap 3).
CREATE TABLE IF NOT EXISTS audit.data_quality_log (
    id             BIGSERIAL,
    checked_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    check_name     TEXT        NOT NULL,
    target_table   TEXT        NOT NULL,
    status         TEXT        NOT NULL,
    failed_rows    BIGINT,
    detail         TEXT
);

CREATE INDEX IF NOT EXISTS idx_weather_observed_at
    ON raw.weather_hourly (observed_at);
CREATE INDEX IF NOT EXISTS idx_aq_observed_at
    ON raw.air_quality_hourly (observed_at);
