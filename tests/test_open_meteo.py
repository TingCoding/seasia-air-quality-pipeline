"""Uji penguraian respons Open-Meteo tanpa memanggil API sungguhan."""

from datetime import date, datetime, timezone

import httpx
import pytest
import respx

from ingestion.clients import open_meteo
from ingestion.config import Location

JAKARTA = Location("jakarta", "Jakarta", "ID", -6.2088, 106.8456, "Asia/Jakarta")

SAMPLE = {
    "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
    "hourly": {
        "time": ["2025-01-01T00:00", "2025-01-01T01:00", "2025-01-01T02:00"],
        "temperature_2m": [26.4, 26.1, None],
    },
}


@respx.mock
def test_fetch_weather_parses_all_hours():
    respx.get(open_meteo.ARCHIVE_URL).mock(
        return_value=httpx.Response(200, json=SAMPLE)
    )
    with httpx.Client() as client:
        result = open_meteo.fetch_weather(
            client, JAKARTA, date(2025, 1, 1), date(2025, 1, 1), ["temperature_2m"]
        )

    assert len(result) == 3
    assert result[0].location_key == "jakarta"
    assert result[0].variable == "temperature_2m"
    assert result[0].unit == "°C"
    assert result[0].source == open_meteo.SOURCE_WEATHER


@respx.mock
def test_times_are_stored_as_utc():
    respx.get(open_meteo.ARCHIVE_URL).mock(
        return_value=httpx.Response(200, json=SAMPLE)
    )
    with httpx.Client() as client:
        result = open_meteo.fetch_weather(
            client, JAKARTA, date(2025, 1, 1), date(2025, 1, 1), ["temperature_2m"]
        )

    assert result[0].observed_at == datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert all(m.observed_at.tzinfo is timezone.utc for m in result)


@respx.mock
def test_null_values_are_kept_not_dropped():
    """Lubang data adalah informasi, bukan sampah — harus ikut tersimpan."""
    respx.get(open_meteo.ARCHIVE_URL).mock(
        return_value=httpx.Response(200, json=SAMPLE)
    )
    with httpx.Client() as client:
        result = open_meteo.fetch_weather(
            client, JAKARTA, date(2025, 1, 1), date(2025, 1, 1), ["temperature_2m"]
        )

    assert result[2].value is None


@respx.mock
def test_retries_then_succeeds_on_server_error():
    route = respx.get(open_meteo.ARCHIVE_URL)
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, json=SAMPLE),
    ]
    with httpx.Client() as client:
        result = open_meteo.fetch_weather(
            client, JAKARTA, date(2025, 1, 1), date(2025, 1, 1), ["temperature_2m"]
        )

    assert route.call_count == 2
    assert len(result) == 3


@respx.mock
def test_gives_up_after_repeated_failures():
    respx.get(open_meteo.ARCHIVE_URL).mock(return_value=httpx.Response(500))
    with httpx.Client() as client, pytest.raises(httpx.HTTPStatusError):
        open_meteo.fetch_weather(
            client, JAKARTA, date(2025, 1, 1), date(2025, 1, 1), ["temperature_2m"]
        )
