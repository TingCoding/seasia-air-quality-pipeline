"""OpenAQ v3 client.

Unlike Open-Meteo, OpenAQ reports from identifiable physical stations. That
brings metadata worth keeping -- who operates the station, what instrument it
uses, when it last reported -- and problems worth handling: dormant stations
still listed, duplicate sensors for one parameter, and units that differ
between providers measuring the same thing.

The station survey (scripts/explore_openaq.py) exists because of this. Which
stations are worth ingesting is a decision made from data, not assumption.

Requires a free API key: https://explore.openaq.org/register
"""

from datetime import date, datetime, time, timedelta, timezone

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import Location
from ..models import Sensor, Station, StationMeasurement

BASE_URL = "https://api.openaq.org/v3"
SOURCE = "openaq"

MAX_PAGE_SIZE = 1000
MAX_PAGES = 50          # guard against an unbounded pagination loop

RETRYABLE = (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError)


class OpenAQError(RuntimeError):
    pass


@retry(
    retry=retry_if_exception_type(RETRYABLE),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _get(client: httpx.Client, path: str, params: dict | None = None) -> dict:
    response = client.get(f"{BASE_URL}{path}", params=params or {}, timeout=45.0)

    # 429 means the rate limit was hit; retrying after a pause is correct.
    # 4xx other than 429 will not improve on retry, so fail immediately with
    # the body attached rather than burning three more attempts.
    if response.status_code == 429:
        response.raise_for_status()
    if 400 <= response.status_code < 500:
        raise OpenAQError(
            f"OpenAQ returned HTTP {response.status_code} for {path}: "
            f"{response.text[:400]}"
        )

    response.raise_for_status()
    return response.json()


def _parse_utc(node: dict | None) -> datetime | None:
    """Read the `utc` field out of an OpenAQ datetime object."""
    if not node:
        return None
    raw = node.get("utc")
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def fetch_stations(
    client: httpx.Client,
    location: Location,
    radius_metres: int,
    limit: int = 200,
) -> list[dict]:
    """Return the raw station payloads near a city centre."""
    payload = _get(
        client,
        "/locations",
        {
            "coordinates": f"{location.latitude},{location.longitude}",
            "radius": radius_metres,
            "limit": min(limit, MAX_PAGE_SIZE),
        },
    )
    return payload.get("results", [])


def fetch_station_by_id(client: httpx.Client, station_id: int) -> dict | None:
    """Fetch one station by its ID.

    Used when ingesting from the pinned registry: the stations are already
    chosen, so there is no need to search by radius and no opportunity for the
    selection to drift between runs.
    """
    payload = _get(client, f"/locations/{station_id}")
    results = payload.get("results") or []
    return results[0] if results else None


def select_stations(
    raw_stations: list[dict],
    parameters: list[str],
    max_stale_days: int,
    max_stations: int,
    now: datetime | None = None,
) -> list[dict]:
    """Apply the station selection rules.

    Three criteria, in order:
      1. the station must expose at least one sensor for a wanted parameter
      2. it must have reported within `max_stale_days`
      3. of those that qualify, keep the most recently active `max_stations`

    Mobile stations are excluded: their coordinates change between readings, so
    they cannot be treated as a fixed point for comparison against a modelled
    value at a fixed coordinate.
    """
    reference = now or datetime.now(timezone.utc)
    cutoff = reference - timedelta(days=max_stale_days)
    wanted = set(parameters)

    eligible = []
    for station in raw_stations:
        if station.get("isMobile"):
            continue

        sensors = station.get("sensors") or []
        if not any((s.get("parameter") or {}).get("name") in wanted for s in sensors):
            continue

        last_seen = _parse_utc(station.get("datetimeLast"))
        if last_seen is None or last_seen < cutoff:
            continue

        eligible.append((last_seen, station))

    eligible.sort(key=lambda pair: pair[0], reverse=True)
    return [station for _, station in eligible[:max_stations]]


def to_station(raw: dict, location_key: str) -> Station:
    coords = raw.get("coordinates") or {}
    return Station(
        station_id=raw["id"],
        location_key=location_key,
        station_name=raw.get("name"),
        provider=(raw.get("provider") or {}).get("name"),
        owner=(raw.get("owner") or {}).get("name"),
        is_monitor=raw.get("isMonitor"),
        is_mobile=raw.get("isMobile"),
        latitude=coords.get("latitude"),
        longitude=coords.get("longitude"),
        timezone=raw.get("timezone"),
        distance_metres=raw.get("distance"),
        first_seen_at=_parse_utc(raw.get("datetimeFirst")),
        last_seen_at=_parse_utc(raw.get("datetimeLast")),
    )


def to_sensors(raw: dict, parameters: list[str]) -> list[Sensor]:
    """Extract the sensors of interest from a station payload.

    A station can expose two sensors for the same parameter. Both are kept:
    deciding which to trust is an analytical question, and resolving it here
    would hide the duplication from the layers meant to detect it.
    """
    wanted = set(parameters)
    sensors = []
    for node in raw.get("sensors") or []:
        parameter = (node.get("parameter") or {})
        name = parameter.get("name")
        if name not in wanted:
            continue
        sensors.append(
            Sensor(
                sensor_id=node["id"],
                station_id=raw["id"],
                parameter=name,
                unit=parameter.get("units"),
            )
        )
    return sensors


def fetch_sensor_hours(
    client: httpx.Client,
    sensor: Sensor,
    location_key: str,
    start: date,
    end: date,
    page_size: int = MAX_PAGE_SIZE,
) -> list[StationMeasurement]:
    """Fetch hourly averages for one sensor, following pagination.

    `/v3/sensors/{id}/hours` returns precomputed hourly means. Each result
    carries a coverage object saying how many readings the mean was built from,
    which is retained rather than dropped.
    """
    measurements: list[StationMeasurement] = []

    # A bare date is interpreted by OpenAQ in the station's local time, which
    # silently shifts the window by the city's UTC offset -- a request for
    # 2025-01-01 in Bangkok returned data from 2024-12-31T17:00Z. Sending an
    # explicit UTC datetime removes the ambiguity. `end` is inclusive of the
    # whole day.
    datetime_from = datetime.combine(start, time.min, tzinfo=timezone.utc)
    datetime_to = datetime.combine(end, time.max, tzinfo=timezone.utc)

    for page in range(1, MAX_PAGES + 1):
        payload = _get(
            client,
            f"/sensors/{sensor.sensor_id}/hours",
            {
                "datetime_from": datetime_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "datetime_to": datetime_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": page_size,
                "page": page,
            },
        )

        results = payload.get("results") or []
        if not results:
            break

        for item in results:
            period = item.get("period") or {}
            observed_at = _parse_utc(period.get("datetimeFrom"))
            if observed_at is None:
                continue

            parameter = item.get("parameter") or {}
            coverage = item.get("coverage") or {}

            measurements.append(
                StationMeasurement(
                    sensor_id=sensor.sensor_id,
                    station_id=sensor.station_id,
                    location_key=location_key,
                    observed_at=observed_at,
                    parameter=parameter.get("name") or sensor.parameter,
                    value=item.get("value"),
                    unit=parameter.get("units") or sensor.unit,
                    coverage_pct=coverage.get("percentComplete"),
                )
            )

        if len(results) < page_size:
            break

    return measurements
