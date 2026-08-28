"""The single data shape used throughout the pipeline.

Every API client returns a list of Measurement, so the loader never needs to
know which source the data came from.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Measurement:
    location_key: str
    observed_at: datetime      # always UTC
    variable: str
    value: float | None
    unit: str | None
    source: str

    def as_row(self) -> tuple:
        return (
            self.location_key,
            self.observed_at,
            self.variable,
            self.value,
            self.unit,
            self.source,
        )


@dataclass(frozen=True, slots=True)
class Station:
    """A physical monitoring station as registered on OpenAQ."""

    station_id: int
    location_key: str
    station_name: str | None
    provider: str | None
    owner: str | None
    is_monitor: bool | None
    is_mobile: bool | None
    latitude: float | None
    longitude: float | None
    timezone: str | None
    distance_metres: float | None
    first_seen_at: datetime | None
    last_seen_at: datetime | None

    def as_row(self) -> tuple:
        return (
            self.station_id, self.location_key, self.station_name,
            self.provider, self.owner, self.is_monitor, self.is_mobile,
            self.latitude, self.longitude, self.timezone,
            self.distance_metres, self.first_seen_at, self.last_seen_at,
        )


@dataclass(frozen=True, slots=True)
class Sensor:
    """One measured parameter at one station.

    A station may expose several sensors, and occasionally two sensors for the
    same parameter -- sometimes even in different units. The sensor, not the
    station, is therefore the unit that measurements attach to.
    """

    sensor_id: int
    station_id: int
    parameter: str
    unit: str | None

    def as_row(self) -> tuple:
        return (self.sensor_id, self.station_id, self.parameter, self.unit)


@dataclass(frozen=True, slots=True)
class StationMeasurement:
    sensor_id: int
    station_id: int
    location_key: str
    observed_at: datetime      # always UTC, start of the hour
    parameter: str
    value: float | None
    unit: str | None
    coverage_pct: float | None

    def as_row(self) -> tuple:
        return (
            self.sensor_id, self.station_id, self.location_key,
            self.observed_at, self.parameter, self.value, self.unit,
            self.coverage_pct,
        )
