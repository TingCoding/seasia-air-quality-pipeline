"""Survey OpenAQ station coverage before committing to a scope.

Prints, per city, which stations exist, which parameters they report, and when
each one last sent data. Run this before writing any ingestion code: the answer
decides which cities are worth including and which are listed but silent.

    python scripts/explore_openaq.py
    python scripts/explore_openaq.py --radius 25000 --limit 100

Note: OpenAQ v3 caps `radius` at 25 km. Larger values are rejected with HTTP 422,
so anything above the cap is clamped here rather than left to fail mid-run.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingestion.config import LOCATIONS  # noqa: E402

load_dotenv()

BASE_URL = "https://api.openaq.org/v3/locations"
MAX_RADIUS_METRES = 25_000
MAX_LIMIT = 1_000


def fetch_locations(client: httpx.Client, lat: float, lon: float,
                    radius: int, limit: int) -> tuple[list[dict], str]:
    """Return (results, found) for one coordinate.

    `found` is what the API reports as the total match count, which may exceed
    the number of rows actually returned.
    """
    response = client.get(
        BASE_URL,
        params={
            "coordinates": f"{lat},{lon}",
            "radius": radius,
            "limit": limit,
        },
        timeout=30.0,
    )

    if response.status_code >= 400:
        # Surface what the API actually objected to; a bare status code is
        # not enough to debug a validation error.
        raise SystemExit(
            f"OpenAQ returned HTTP {response.status_code} for "
            f"{lat},{lon}\n{response.text[:600]}"
        )

    payload = response.json()
    found = str((payload.get("meta") or {}).get("found", "?"))
    return payload.get("results", []), found


def describe_age(iso_timestamp: str | None) -> str:
    if not iso_timestamp:
        return "no data"
    parsed = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    days = (datetime.now(timezone.utc) - parsed).days
    if days > 365:
        return f"{days // 365}y ago"
    return f"{days}d ago"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radius", type=int, default=MAX_RADIUS_METRES,
                        help=f"search radius in metres (max {MAX_RADIUS_METRES})")
    parser.add_argument("--limit", type=int, default=100,
                        help=f"stations per city (max {MAX_LIMIT})")
    args = parser.parse_args()

    radius = min(args.radius, MAX_RADIUS_METRES)
    if args.radius > MAX_RADIUS_METRES:
        print(f"note: radius clamped to {MAX_RADIUS_METRES} m, the API maximum\n")

    limit = min(args.limit, MAX_LIMIT)

    api_key = os.getenv("OPENAQ_API_KEY")
    if not api_key:
        raise SystemExit("OPENAQ_API_KEY is not set in .env")

    headers = {"X-API-Key": api_key, "User-Agent": "seasia-aq-pipeline/0.1"}

    with httpx.Client(headers=headers) as client:
        for loc in LOCATIONS:
            stations, found = fetch_locations(
                client, loc.latitude, loc.longitude, radius, limit
            )

            live = [s for s in stations if (s.get("datetimeLast") or {}).get("utc")]

            print(f"\n{loc.city}  —  {found} found, {len(stations)} returned, "
                  f"{len(live)} with data")
            print(f"  {'id':>7}  {'name':<26} {'provider':<15} "
                  f"{'last seen':>10}  parameters")
            print("  " + "-" * 84)

            if not stations:
                print("  none found within the search radius")
                continue

            for s in sorted(
                stations,
                key=lambda x: (x.get("datetimeLast") or {}).get("utc") or "",
                reverse=True,
            ):
                params = ", ".join(
                    f"{sensor['parameter']['name']} ({sensor['parameter']['units']})"
                    for sensor in s.get("sensors", [])
                ) or "-"
                last = (s.get("datetimeLast") or {}).get("utc")
                provider = (s.get("provider") or {}).get("name", "-")

                print(
                    f"  {str(s['id']):>7}  {str(s['name'])[:26]:<26} "
                    f"{provider[:15]:<15} {describe_age(last):>10}  {params}"
                )

    return 0


if __name__ == "__main__":
    sys.exit(main())
