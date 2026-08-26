"""Database connection and idempotent writes into the raw layer."""

import os
from collections.abc import Iterable, Iterator
from contextlib import contextmanager

import psycopg
from dotenv import load_dotenv

from .models import Measurement

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
