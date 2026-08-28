"""Tests for the pinned station registry.

The registry exists to make ingestion reproducible, so the round trip through
CSV must preserve exactly what was written -- including the awkward cases the
API actually produces: empty provider names, missing coordinates, and stations
that have never reported.
"""

from datetime import date

import pytest

from ingestion.station_registry import (
    PinnedStation,
    read_registry,
    to_pinned,
    write_registry,
)


def make(station_id=135, location_key="bangkok", **overrides):
    defaults = dict(
        location_key=location_key,
        station_id=station_id,
        station_name="Chatuchak Park",
        provider="Air4Thai",
        owner="Gov",
        is_monitor=True,
        latitude=13.8,
        longitude=100.55,
        timezone="Asia/Bangkok",
        first_seen_at="2020-01-01T00:00:00Z",
        last_seen_at="2026-08-27T00:00:00Z",
        selected_on="2026-08-28",
    )
    defaults.update(overrides)
    return PinnedStation(**defaults)


def test_round_trip_preserves_values(tmp_path):
    path = tmp_path / "openaq_stations.csv"
    original = [make(135), make(701, station_name="Sukhothai Thammathirat")]

    write_registry(original, path)
    restored = read_registry(path)

    assert restored == original


def test_rows_are_written_in_a_stable_order(tmp_path):
    """A stable order keeps git diffs meaningful when the list is regenerated."""
    path = tmp_path / "openaq_stations.csv"
    write_registry([make(701), make(135), make(9, location_key="jakarta")], path)

    restored = read_registry(path)
    assert [(s.location_key, s.station_id) for s in restored] == [
        ("bangkok", 135),
        ("bangkok", 701),
        ("jakarta", 9),
    ]


def test_missing_registry_gives_an_actionable_error(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        read_registry(tmp_path / "does_not_exist.csv")
    assert "--discover" in str(excinfo.value)


def test_handles_stations_with_missing_metadata(tmp_path):
    """Several providers omit owner, coordinates, or any reporting history."""
    path = tmp_path / "openaq_stations.csv"
    sparse = make(
        223262,
        station_name="Cilandek",
        provider="HabitatMap",
        owner="",
        first_seen_at="",
        last_seen_at="",
    )
    write_registry([sparse], path)
    restored = read_registry(path)

    assert restored[0].owner == ""
    assert restored[0].last_seen_at == ""


def test_to_pinned_maps_the_api_payload():
    raw = {
        "id": 225568,
        "name": "Bang Khen District Office",
        "provider": {"name": "Air4Thai"},
        "owner": {"name": "Unknown Governmental Organization"},
        "isMonitor": True,
        "timezone": "Asia/Bangkok",
        "coordinates": {"latitude": 13.85, "longitude": 100.58},
        "datetimeFirst": {"utc": "2019-05-01T00:00:00Z"},
        "datetimeLast": {"utc": "2026-08-28T03:00:00Z"},
    }
    result = to_pinned(raw, "bangkok", date(2026, 8, 28))

    assert result.station_id == 225568
    assert result.provider == "Air4Thai"
    assert result.selected_on == "2026-08-28"
    assert result.last_seen_at == "2026-08-28T03:00:00Z"


def test_to_pinned_survives_an_empty_payload():
    result = to_pinned({"id": 7}, "jakarta", date(2026, 8, 28))

    assert result.station_id == 7
    assert result.station_name == ""
    assert result.provider == ""
    assert result.latitude == 0.0


# ---------------------------------------------- tolerance for edited files

@pytest.mark.parametrize(
    "written,expected",
    [
        ("2026-08-28", "2026-08-28"),
        ("28/08/2026", "2026-08-28"),   # what a spreadsheet leaves behind
        ("28-08-2026", "2026-08-28"),
        ("", ""),
        ("not a date", "not a date"),   # passed through, not silently dropped
    ],
)
def test_selected_on_accepts_spreadsheet_formats(written, expected):
    from ingestion.station_registry import normalise_date

    assert normalise_date(written) == expected


def test_reading_a_spreadsheet_edited_file(tmp_path):
    """A registry saved through Excel must still load.

    Excel rewrites the date as DD/MM/YYYY and booleans as TRUE/FALSE. Neither
    should break ingestion, because a file meant for human review will be
    opened by humans using the tools they have.
    """
    path = tmp_path / "openaq_stations.csv"
    path.write_text(
        "location_key,station_id,station_name,provider,owner,is_monitor,"
        "latitude,longitude,timezone,first_seen_at,last_seen_at,selected_on\n"
        "bangkok,701,Sukhothai,Air4Thai,Gov,TRUE,13.9,100.5,Asia/Bangkok,"
        "2016-01-30T02:00:00Z,2026-08-28T07:00:00Z,28/08/2026\n",
        encoding="utf-8",
    )

    restored = read_registry(path)

    assert len(restored) == 1
    assert restored[0].is_monitor is True
    assert restored[0].selected_on == "2026-08-28"
