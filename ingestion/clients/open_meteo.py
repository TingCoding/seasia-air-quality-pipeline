"""Klien Open-Meteo.

Dua endpoint dipakai: arsip cuaca historis dan kualitas udara. Keduanya
mengembalikan struktur yang sama — objek `hourly` berisi daftar waktu dan
satu daftar nilai per variabel — sehingga penguraiannya bisa dipakai bersama.

Open-Meteo tidak memerlukan API key.
"""

from datetime import date, datetime, timezone

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import Location
from ..models import Measurement

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

SOURCE_WEATHER = "open-meteo-archive"
SOURCE_AIR_QUALITY = "open-meteo-air-quality"

RETRYABLE = (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError)


@retry(
    retry=retry_if_exception_type(RETRYABLE),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _get(client: httpx.Client, url: str, params: dict) -> dict:
    """Satu panggilan HTTP dengan percobaan ulang bertahap.

    Jeda tunggu digandakan setiap kegagalan agar tidak membebani API gratis
    saat sedang bermasalah.
    """
    response = client.get(url, params=params, timeout=30.0)
    response.raise_for_status()
    return response.json()


def _parse_hourly(payload: dict, location_key: str, source: str) -> list[Measurement]:
    """Ubah respons Open-Meteo menjadi daftar Measurement.

    Nilai null dipertahankan, tidak dibuang. Lubang data adalah informasi —
    membuangnya di sini akan menyembunyikan masalah kualitas data yang justru
    ingin kita deteksi di Tahap 3.
    """
    hourly = payload.get("hourly") or {}
    units = payload.get("hourly_units") or {}
    times = hourly.get("time") or []

    measurements: list[Measurement] = []
    for variable, values in hourly.items():
        if variable == "time":
            continue
        for iso_time, value in zip(times, values, strict=True):
            measurements.append(
                Measurement(
                    location_key=location_key,
                    observed_at=_to_utc(iso_time),
                    variable=variable,
                    value=value,
                    unit=units.get(variable),
                    source=source,
                )
            )
    return measurements


def _to_utc(iso_time: str) -> datetime:
    """Open-Meteo mengembalikan waktu tanpa penanda zona saat timezone=UTC."""
    parsed = datetime.fromisoformat(iso_time)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def fetch_weather(
    client: httpx.Client,
    location: Location,
    start: date,
    end: date,
    variables: list[str],
) -> list[Measurement]:
    payload = _get(
        client,
        ARCHIVE_URL,
        {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": ",".join(variables),
            "timezone": "UTC",
        },
    )
    return _parse_hourly(payload, location.key, SOURCE_WEATHER)


def fetch_air_quality(
    client: httpx.Client,
    location: Location,
    start: date,
    end: date,
    variables: list[str],
) -> list[Measurement]:
    payload = _get(
        client,
        AIR_QUALITY_URL,
        {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": ",".join(variables),
            "timezone": "UTC",
        },
    )
    return _parse_hourly(payload, location.key, SOURCE_AIR_QUALITY)
