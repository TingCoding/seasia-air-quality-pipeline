"""Bentuk data tunggal yang dipakai seluruh pipeline.

Semua klien API mengembalikan daftar Measurement, sehingga pemuat data tidak
perlu tahu dari sumber mana data berasal.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Measurement:
    location_key: str
    observed_at: datetime      # selalu UTC
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
