"""OpenAQ ingestion entry point.

Kept separate from run_ingest because the two sources behave differently.
Open-Meteo answers a whole date range for a coordinate in one request; OpenAQ
requires resolving stations, then their sensors, then paginating through hourly
values per sensor.

Ingestion runs in two distinct modes:

  --discover  searches near each city, applies the selection rules, and writes
              the result to dbt/seeds/openaq_stations.csv for review. Loads
              nothing.

  (default)   reads that file and loads measurements for exactly those
              stations. The registry is the only input, so the same command
              always touches the same stations.

Examples:
    python -m ingestion.run_openaq --discover
    python -m ingestion.run_openaq --start 2025-01-01 --end 2025-12-31
    python -m ingestion.run_openaq --start 2025-01-01 --end 2025-03-31 \
        --locations bangkok jakarta
"""

import argparse
import logging
import os
import sys
import time
from datetime import date

import httpx

from . import config
from .clients import openaq
from .db import (
    connection,
    upsert_sensors,
    upsert_station_measurements,
    upsert_stations,
)
from .run_ingest import select_locations
from .station_registry import (
    REGISTRY_PATH,
    read_registry,
    to_pinned,
    write_registry,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("openaq")

# OpenAQ enforces a rate limit per API key. Pausing between sensor requests
# keeps well inside it rather than relying on retries to absorb 429s.
REQUEST_DELAY_SECONDS = 1.2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load OpenAQ station measurements.")
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--locations", nargs="*", default=None)
    parser.add_argument(
        "--discover",
        action="store_true",
        help="propose a station list and write it to the registry, loading nothing",
    )
    parser.add_argument(
        "--max-stations",
        type=int,
        default=config.OPENAQ_MAX_STATIONS_PER_CITY,
        help="stations per city, used with --discover",
    )
    return parser.parse_args(argv)


def build_client() -> httpx.Client:
    api_key = os.getenv("OPENAQ_API_KEY")
    if not api_key:
        raise SystemExit("OPENAQ_API_KEY is not set in .env")
    return httpx.Client(
        headers={"X-API-Key": api_key, "User-Agent": "seasia-aq-pipeline/0.1"}
    )


def discover(locations, max_stations: int) -> int:
    """Propose a station list and write it to the registry for review."""
    today = date.today()
    pinned = []

    with build_client() as client:
        for loc in locations:
            raw_stations = openaq.fetch_stations(
                client, loc, config.OPENAQ_RADIUS_METRES
            )
            chosen = openaq.select_stations(
                raw_stations,
                parameters=config.OPENAQ_PARAMETERS,
                max_stale_days=config.OPENAQ_MAX_STALE_DAYS,
                max_stations=max_stations,
            )

            log.info(
                "%-13s %3d found, %d selected",
                loc.key, len(raw_stations), len(chosen),
            )
            if not chosen:
                log.warning(
                    "%-13s nothing meets the rules (active within %d days, "
                    "reporting %s)",
                    loc.key, config.OPENAQ_MAX_STALE_DAYS,
                    "/".join(config.OPENAQ_PARAMETERS),
                )

            for raw in chosen:
                station = to_pinned(raw, loc.key, today)
                pinned.append(station)
                log.info(
                    "    %-9s %-28s %-16s last seen %s",
                    station.station_id,
                    station.station_name[:28],
                    station.provider[:16],
                    station.last_seen_at[:10] or "-",
                )

    path = write_registry(pinned)
    log.info("Wrote %d stations to %s", len(pinned), path)
    log.info("Review the file, adjust it if needed, then commit it.")
    return 0


def load(locations, start: date, end: date) -> int:
    """Load measurements for the stations named in the registry."""
    wanted_keys = {loc.key for loc in locations}
    registry = [s for s in read_registry() if s.location_key in wanted_keys]

    if not registry:
        raise SystemExit(
            f"No stations in {REGISTRY_PATH.name} for the requested locations.\n"
            "Run --discover first."
        )

    log.info(
        "Loading %s to %s for %d pinned stations across %d locations",
        start, end, len(registry), len(wanted_keys),
    )

    total_rows = 0

    with build_client() as client, connection() as conn:
        for pinned in registry:
            raw = openaq.fetch_station_by_id(client, pinned.station_id)
            if raw is None:
                log.warning(
                    "station %s (%s) is in the registry but the API no longer "
                    "returns it", pinned.station_id, pinned.station_name,
                )
                continue

            station = openaq.to_station(raw, pinned.location_key)
            sensors = openaq.to_sensors(raw, config.OPENAQ_PARAMETERS)

            upsert_stations(conn, [station])
            upsert_sensors(conn, sensors)
            conn.commit()

            log.info(
                "%-13s %-9s %-26s %d sensors",
                pinned.location_key, station.station_id,
                (station.station_name or "")[:26], len(sensors),
            )

            for sensor in sensors:
                measurements = openaq.fetch_sensor_hours(
                    client, sensor, pinned.location_key, start, end
                )
                written = upsert_station_measurements(conn, measurements)
                conn.commit()

                log.info(
                    "    sensor %-9s %-6s %6d rows",
                    sensor.sensor_id, sensor.parameter, written,
                )
                total_rows += written
                time.sleep(REQUEST_DELAY_SECONDS)

    log.info("Done. %d rows written in total.", total_rows)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    locations = select_locations(args.locations)

    if args.discover:
        return discover(locations, args.max_stations)

    if args.start is None or args.end is None:
        raise SystemExit("--start and --end are required unless --discover is used")
    if args.start > args.end:
        raise SystemExit("--start must not be after --end")

    return load(locations, args.start, args.end)


if __name__ == "__main__":
    sys.exit(main())
