"""Database connection and idempotent writes into the raw layer."""

import os
from collections.abc import Iterable, Iterator
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv

from .models import Measurement, Sensor, Station, StationMeasurement

load_dotenv()

ALLOWED_TABLES = {"raw.weather_hourly", "raw.air_quality_hourly"}


def build_dsn() -> str:
    return (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'air_quality')} "
        f"user={os.getenv('POSTGRES_USER', 'aq_user')} "
        f"password={os.getenv('POSTGRES_PASSWORD', '')}"
    )


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(build_dsn())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_measurements(
    conn: psycopg.Connection,
    table: str,
    measurements: Iterable[Measurement],
    batch_size: int = 5000,
) -> int:
    """Write measurements into a raw table.

    Uses ON CONFLICT DO UPDATE against the composite primary key, so re-running
    the same date range never duplicates rows. This is what makes ingestion
    idempotent.
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Unknown table: {table}")

    sql = f"""
        INSERT INTO {table}
            (location_key, observed_at, variable, value, unit, source)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (location_key, observed_at, variable, source)
        DO UPDATE SET
            value       = EXCLUDED.value,
            unit        = EXCLUDED.unit,
            ingested_at = now()
    """

    total, batch = 0, []
    with conn.cursor() as cur:
        for m in measurements:
            batch.append(m.as_row())
            if len(batch) >= batch_size:
                cur.executemany(sql, batch)
                total += len(batch)
                batch.clear()
        if batch:
            cur.executemany(sql, batch)
            total += len(batch)
    return total


# --------------------------------------------------------------- OpenAQ
#
# Each of these writes is idempotent in the same way as the Open-Meteo loader:
# a natural primary key plus ON CONFLICT DO UPDATE, so a re-run refreshes rows
# instead of duplicating them.


def upsert_stations(conn: psycopg.Connection, stations: Iterable[Station]) -> int:
    sql = """
        INSERT INTO raw.openaq_stations
            (station_id, location_key, station_name, provider, owner,
             is_monitor, is_mobile, latitude, longitude, timezone,
             distance_metres, first_seen_at, last_seen_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (station_id) DO UPDATE SET
            location_key    = EXCLUDED.location_key,
            station_name    = EXCLUDED.station_name,
            provider        = EXCLUDED.provider,
            owner           = EXCLUDED.owner,
            is_monitor      = EXCLUDED.is_monitor,
            is_mobile       = EXCLUDED.is_mobile,
            latitude        = EXCLUDED.latitude,
            longitude       = EXCLUDED.longitude,
            timezone        = EXCLUDED.timezone,
            distance_metres = EXCLUDED.distance_metres,
            first_seen_at   = EXCLUDED.first_seen_at,
            last_seen_at    = EXCLUDED.last_seen_at,
            ingested_at     = now()
    """
    rows = [s.as_row() for s in stations]
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


def upsert_sensors(conn: psycopg.Connection, sensors: Iterable[Sensor]) -> int:
    sql = """
        INSERT INTO raw.openaq_sensors (sensor_id, station_id, parameter, unit)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (sensor_id) DO UPDATE SET
            station_id  = EXCLUDED.station_id,
            parameter   = EXCLUDED.parameter,
            unit        = EXCLUDED.unit,
            ingested_at = now()
    """
    rows = [s.as_row() for s in sensors]
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


def upsert_station_measurements(
    conn: psycopg.Connection,
    measurements: Iterable[StationMeasurement],
    batch_size: int = 5000,
) -> int:
    sql = """
        INSERT INTO raw.openaq_measurements
            (sensor_id, station_id, location_key, observed_at,
             parameter, value, unit, coverage_pct)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sensor_id, observed_at) DO UPDATE SET
            value        = EXCLUDED.value,
            unit         = EXCLUDED.unit,
            coverage_pct = EXCLUDED.coverage_pct,
            ingested_at  = now()
    """
    total, batch = 0, []
    with conn.cursor() as cur:
        for m in measurements:
            batch.append(m.as_row())
            if len(batch) >= batch_size:
                cur.executemany(sql, batch)
                total += len(batch)
                batch.clear()
        if batch:
            cur.executemany(sql, batch)
            total += len(batch)
    return total
