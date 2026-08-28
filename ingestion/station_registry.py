"""The pinned list of OpenAQ stations this pipeline ingests.

Station selection used to be re-derived on every run by taking the most
recently active stations near each city. That is not reproducible: because
`datetimeLast` advances continuously, two runs hours apart chose different
stations, and the warehouse ended up holding a blend nobody could account for.

Selection is now a decision made once and written down. `--discover` proposes a
list, a human reviews it, and it is committed to the repository. Ingestion reads
that file and nothing else, so the same command always loads the same stations.

The file lives in dbt/seeds so it serves twice: as the input to ingestion, and
as the seed behind the station dimension. Comparing what was chosen against what
the API reports today is then a query, not an investigation.
"""

import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = PROJECT_ROOT / "dbt" / "seeds" / "openaq_stations.csv"

FIELDNAMES = [
    "location_key",
    "station_id",
    "station_name",
    "provider",
    "owner",
    "is_monitor",
    "latitude",
    "longitude",
    "timezone",
    "first_seen_at",
    "last_seen_at",
    "selected_on",
]


@dataclass(frozen=True)
class PinnedStation:
    location_key: str
    station_id: int
    station_name: str
    provider: str
    owner: str
    is_monitor: bool
    latitude: float
    longitude: float
    timezone: str
    first_seen_at: str
    last_seen_at: str
    selected_on: str


def normalise_date(value: str) -> str:
    """Return an ISO date, accepting the formats a spreadsheet may leave behind.

    The registry is meant to be reviewed by hand, and opening a CSV in a
    spreadsheet application rewrites dates on save -- 2026-08-28 becomes
    28/08/2026. Rather than forbidding that, the reader accepts it and
    normalises. Tools should tolerate how people actually work.
    """
    value = (value or "").strip()
    if not value:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return value


def _clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def write_registry(stations: list[PinnedStation], path: Path = REGISTRY_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for station in sorted(stations, key=lambda s: (s.location_key, s.station_id)):
            writer.writerow({k: _clean(v) for k, v in asdict(station).items()})
    return path


def read_registry(path: Path = REGISTRY_PATH) -> list[PinnedStation]:
    if not path.exists():
        raise SystemExit(
            f"No station registry at {path}.\n"
            "Run discovery first:\n"
            "    python -m ingestion.run_openaq --discover\n"
            "then review the file and commit it."
        )

    stations = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            stations.append(
                PinnedStation(
                    location_key=row["location_key"],
                    station_id=int(row["station_id"]),
                    station_name=row["station_name"],
                    provider=row["provider"],
                    owner=row["owner"],
                    is_monitor=row["is_monitor"].lower() in ("true", "1", "yes"),
                    latitude=float(row["latitude"]) if row["latitude"] else 0.0,
                    longitude=float(row["longitude"]) if row["longitude"] else 0.0,
                    timezone=row["timezone"],
                    first_seen_at=row["first_seen_at"],
                    last_seen_at=row["last_seen_at"],
                    selected_on=normalise_date(row["selected_on"]),
                )
            )
    return stations


def to_pinned(raw: dict, location_key: str, selected_on: date) -> PinnedStation:
    coords = raw.get("coordinates") or {}
    return PinnedStation(
        location_key=location_key,
        station_id=raw["id"],
        station_name=raw.get("name") or "",
        provider=(raw.get("provider") or {}).get("name", ""),
        owner=(raw.get("owner") or {}).get("name", ""),
        is_monitor=bool(raw.get("isMonitor")),
        latitude=coords.get("latitude") or 0.0,
        longitude=coords.get("longitude") or 0.0,
        timezone=raw.get("timezone") or "",
        first_seen_at=((raw.get("datetimeFirst") or {}).get("utc") or ""),
        last_seen_at=((raw.get("datetimeLast") or {}).get("utc") or ""),
        selected_on=selected_on.isoformat(),
    )
