"""Tests for the OpenAQ client.

The station selection rules carry real consequences -- they decide which data
enters the warehouse -- so they are tested against the shapes actually observed
in the API survey: dormant stations, stations with no data at all, duplicate
sensors, and mobile units.
"""

from datetime import date, datetime, timezone

import httpx
import pytest
import respx

from ingestion.clients import openaq
from ingestion.config import Location

BANGKOK = Location("bangkok", "Bangkok", "TH", 13.7563, 100.5018, "Asia/Bangkok")

NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)


def station(station_id, *, last=None, first="2020-01-01T00:00:00Z",
            params=("pm25",), mobile=False, name="Test", provider="Air4Thai"):
    return {
        "id": station_id,
        "name": name,
        "provider": {"name": provider},
        "owner": {"name": "Gov"},
        "isMobile": mobile,
        "isMonitor": True,
        "timezone": "Asia/Bangkok",
        "coordinates": {"latitude": 13.7, "longitude": 100.5},
        "distance": 1234.5,
        "sensors": [
            {"id": 1000 + i, "parameter": {"name": p, "units": "µg/m³"}}
            for i, p in enumerate(params)
        ],
        "datetimeFirst": {"utc": first} if first else None,
        "datetimeLast": {"utc": last} if last else None,
    }


PARAMS = ["pm25", "pm10"]


# ------------------------------------------------------------ selection rules

def test_drops_stations_that_never_reported():
    """HabitatMap test entries appear in the API with no data at all."""
    result = openaq.select_stations(
        [station(1, last=None)], PARAMS, 90, 5, now=NOW
    )
    assert result == []


def test_drops_dormant_stations():
    """A station last seen in 2016 is still listed but is of no use."""
    result = openaq.select_stations(
        [station(1, last="2016-11-09T16:00:00Z")], PARAMS, 90, 5, now=NOW
    )
    assert result == []


def test_keeps_recently_active_stations():
    result = openaq.select_stations(
        [station(1, last="2026-08-26T10:00:00Z")], PARAMS, 90, 5, now=NOW
    )
    assert [s["id"] for s in result] == [1]


def test_drops_stations_without_a_wanted_parameter():
    """Some stations report only black carbon, which is out of scope."""
    result = openaq.select_stations(
        [station(1, last="2026-08-26T10:00:00Z", params=("bc_370",))],
        PARAMS, 90, 5, now=NOW,
    )
    assert result == []


def test_drops_mobile_stations():
    result = openaq.select_stations(
        [station(1, last="2026-08-26T10:00:00Z", mobile=True)],
        PARAMS, 90, 5, now=NOW,
    )
    assert result == []


def test_prefers_the_most_recently_active_when_capped():
    stations = [
        station(1, last="2026-06-01T00:00:00Z"),
        station(2, last="2026-08-26T00:00:00Z"),
        station(3, last="2026-07-15T00:00:00Z"),
    ]
    result = openaq.select_stations(stations, PARAMS, 90, 2, now=NOW)
    assert [s["id"] for s in result] == [2, 3]


# ------------------------------------------------------------------- mapping

def test_duplicate_sensors_for_one_parameter_are_both_kept():
    """Air4Thai stations frequently expose pm25 twice. Both must survive."""
    raw = station(1, last="2026-08-26T00:00:00Z", params=("pm25", "pm25"))
    sensors = openaq.to_sensors(raw, PARAMS)
    assert len(sensors) == 2
    assert {s.sensor_id for s in sensors} == {1000, 1001}


def test_to_station_reads_nested_metadata():
    raw = station(42, last="2026-08-26T00:00:00Z", name="Chatuchak Park")
    result = openaq.to_station(raw, "bangkok")

    assert result.station_id == 42
    assert result.location_key == "bangkok"
    assert result.station_name == "Chatuchak Park"
    assert result.provider == "Air4Thai"
    assert result.last_seen_at == datetime(2026, 8, 26, tzinfo=timezone.utc)


def test_to_station_survives_missing_metadata():
    """Several providers omit owner, licence or coordinates entirely."""
    raw = {"id": 7, "name": None, "sensors": [],
           "datetimeFirst": None, "datetimeLast": None}
    result = openaq.to_station(raw, "jakarta")

    assert result.station_id == 7
    assert result.provider is None
    assert result.latitude is None
    assert result.last_seen_at is None


# ------------------------------------------------------------- measurements

HOURS_PAGE = {
    "meta": {"page": 1, "limit": 1000, "found": 2},
    "results": [
        {
            "value": 23.4,
            "parameter": {"id": 2, "name": "pm25", "units": "µg/m³"},
            "period": {
                "label": "hour",
                "datetimeFrom": {"utc": "2025-01-01T00:00:00Z"},
                "datetimeTo": {"utc": "2025-01-01T01:00:00Z"},
            },
            "coverage": {"expectedCount": 60, "observedCount": 58,
                         "percentComplete": 96.7},
        },
        {
            "value": None,
            "parameter": {"id": 2, "name": "pm25", "units": "µg/m³"},
            "period": {
                "label": "hour",
                "datetimeFrom": {"utc": "2025-01-01T01:00:00Z"},
                "datetimeTo": {"utc": "2025-01-01T02:00:00Z"},
            },
            "coverage": {"expectedCount": 60, "observedCount": 0,
                         "percentComplete": 0.0},
        },
    ],
}

SENSOR = openaq.Sensor(sensor_id=5047, station_id=2537,
                       parameter="pm25", unit="µg/m³")


@respx.mock
def test_fetch_sensor_hours_parses_period_and_coverage():
    respx.get(f"{openaq.BASE_URL}/sensors/5047/hours").mock(
        return_value=httpx.Response(200, json=HOURS_PAGE)
    )
    with httpx.Client() as client:
        result = openaq.fetch_sensor_hours(
            client, SENSOR, "bangkok", date(2025, 1, 1), date(2025, 1, 2)
        )

    assert len(result) == 2
    first = result[0]
    assert first.observed_at == datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert first.value == 23.4
    assert first.unit == "µg/m³"
    assert first.coverage_pct == 96.7
    assert first.station_id == 2537


@respx.mock
def test_hours_with_no_readings_are_kept_with_null_value():
    """An hour the sensor missed is data, not absence of data."""
    respx.get(f"{openaq.BASE_URL}/sensors/5047/hours").mock(
        return_value=httpx.Response(200, json=HOURS_PAGE)
    )
    with httpx.Client() as client:
        result = openaq.fetch_sensor_hours(
            client, SENSOR, "bangkok", date(2025, 1, 1), date(2025, 1, 2)
        )

    assert result[1].value is None
    assert result[1].coverage_pct == 0.0


@respx.mock
def test_pagination_follows_a_full_page_then_stops_when_empty():
    """A full page means there may be more; an empty page means there is not."""
    route = respx.get(f"{openaq.BASE_URL}/sensors/5047/hours")
    route.side_effect = [
        httpx.Response(200, json=HOURS_PAGE),                      # full page
        httpx.Response(200, json={"meta": {}, "results": []}),     # nothing left
    ]

    with httpx.Client() as client:
        result = openaq.fetch_sensor_hours(
            client, SENSOR, "bangkok",
            date(2025, 1, 1), date(2025, 1, 2), page_size=2,
        )

    assert route.call_count == 2
    assert len(result) == 2


@respx.mock
def test_pagination_stops_immediately_on_a_short_page():
    """Fewer results than the page size means the last page has been reached."""
    route = respx.get(f"{openaq.BASE_URL}/sensors/5047/hours").mock(
        return_value=httpx.Response(200, json=HOURS_PAGE)
    )

    with httpx.Client() as client:
        result = openaq.fetch_sensor_hours(
            client, SENSOR, "bangkok",
            date(2025, 1, 1), date(2025, 1, 2), page_size=10,
        )

    assert route.call_count == 1
    assert len(result) == 2


@respx.mock
def test_client_error_fails_fast_with_the_api_message():
    """A 422 will not improve on retry, so it must not burn four attempts."""
    route = respx.get(f"{openaq.BASE_URL}/sensors/5047/hours").mock(
        return_value=httpx.Response(422, text="radius exceeds maximum")
    )
    with httpx.Client() as client, pytest.raises(openaq.OpenAQError) as excinfo:
        openaq.fetch_sensor_hours(
            client, SENSOR, "bangkok", date(2025, 1, 1), date(2025, 1, 2)
        )

    assert route.call_count == 1
    assert "radius exceeds maximum" in str(excinfo.value)


@respx.mock
def test_time_window_is_sent_as_explicit_utc():
    """A bare date is read by OpenAQ in station-local time, shifting the window.

    Requesting 2025-01-01 for Bangkok previously returned data starting at
    2024-12-31T17:00Z -- the UTC+7 offset. The request must therefore carry an
    explicit UTC datetime.
    """
    route = respx.get(f"{openaq.BASE_URL}/sensors/5047/hours").mock(
        return_value=httpx.Response(200, json={"meta": {}, "results": []})
    )
    with httpx.Client() as client:
        openaq.fetch_sensor_hours(
            client, SENSOR, "bangkok", date(2025, 1, 1), date(2025, 1, 7)
        )

    params = route.calls[0].request.url.params
    assert params["datetime_from"] == "2025-01-01T00:00:00Z"
    assert params["datetime_to"] == "2025-01-07T23:59:59Z"


@respx.mock
def test_fetch_station_by_id_returns_the_single_result():
    respx.get(f"{openaq.BASE_URL}/locations/225568").mock(
        return_value=httpx.Response(
            200, json={"results": [{"id": 225568, "name": "Bang Khen"}]}
        )
    )
    with httpx.Client() as client:
        result = openaq.fetch_station_by_id(client, 225568)

    assert result["id"] == 225568


@respx.mock
def test_fetch_station_by_id_returns_none_when_gone():
    """A pinned station may be withdrawn upstream; that must not crash a run."""
    respx.get(f"{openaq.BASE_URL}/locations/999").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    with httpx.Client() as client:
        assert openaq.fetch_station_by_id(client, 999) is None
