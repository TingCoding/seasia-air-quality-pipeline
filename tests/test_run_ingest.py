import pytest

from ingestion.run_ingest import parse_args, select_locations


def test_selects_all_locations_by_default():
    assert len(select_locations(None)) == 6


def test_selects_subset_in_requested_order():
    result = select_locations(["singapore", "jakarta"])
    assert [loc.key for loc in result] == ["singapore", "jakarta"]


def test_rejects_unknown_location():
    with pytest.raises(SystemExit):
        select_locations(["atlantis"])


def test_parses_dates():
    args = parse_args(["--start", "2025-01-01", "--end", "2025-01-31"])
    assert args.start.year == 2025
    assert args.end.day == 31
