"""Titik masuk ingestion.

Contoh:
    python -m ingestion.run_ingest --start 2025-01-01 --end 2025-01-07
    python -m ingestion.run_ingest --start 2025-01-01 --end 2025-01-07 \
        --locations jakarta singapore
"""

import argparse
import logging
import sys
import time
from datetime import date

import httpx

from . import config
from .clients import open_meteo
from .db import connection, upsert_measurements

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest")

# Jeda antar permintaan. Open-Meteo gratis untuk penggunaan non-komersial,
# jadi kita membatasi diri sendiri agar tidak menyalahgunakannya.
REQUEST_DELAY_SECONDS = 1.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Muat data cuaca dan kualitas udara.")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--locations",
        nargs="*",
        default=None,
        help="kunci lokasi; kosongkan untuk memuat semua",
    )
    parser.add_argument(
        "--skip-air-quality",
        action="store_true",
        help="hanya muat data cuaca",
    )
    return parser.parse_args(argv)


def select_locations(keys: list[str] | None) -> list[config.Location]:
    if not keys:
        return config.LOCATIONS
    known = {loc.key: loc for loc in config.LOCATIONS}
    unknown = set(keys) - known.keys()
    if unknown:
        raise SystemExit(f"Lokasi tidak dikenal: {', '.join(sorted(unknown))}")
    return [known[k] for k in keys]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.start > args.end:
        raise SystemExit("--start tidak boleh setelah --end")

    locations = select_locations(args.locations)
    log.info(
        "Memuat %s sampai %s untuk %d lokasi",
        args.start, args.end, len(locations),
    )

    total = 0
    with httpx.Client(headers={"User-Agent": "seasia-aq-pipeline/0.1"}) as client, \
            connection() as conn:
        for loc in locations:
            weather = open_meteo.fetch_weather(
                client, loc, args.start, args.end, config.WEATHER_VARIABLES
            )
            written = upsert_measurements(conn, "raw.weather_hourly", weather)
            log.info("%-13s cuaca         %6d baris", loc.key, written)
            total += written
            time.sleep(REQUEST_DELAY_SECONDS)

            if args.skip_air_quality:
                continue

            air = open_meteo.fetch_air_quality(
                client, loc, args.start, args.end, config.AIR_QUALITY_VARIABLES
            )
            written = upsert_measurements(conn, "raw.air_quality_hourly", air)
            log.info("%-13s kualitas udara %5d baris", loc.key, written)
            total += written
            time.sleep(REQUEST_DELAY_SECONDS)

    log.info("Selesai. Total %d baris ditulis.", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
