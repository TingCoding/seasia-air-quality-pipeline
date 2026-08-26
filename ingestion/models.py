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
