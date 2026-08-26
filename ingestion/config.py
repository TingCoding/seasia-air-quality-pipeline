"""Central configuration: which locations to load and which variables to fetch.

The city list lives here so the project's scope can change without touching
ingestion code. Adjust it after checking station availability per city.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    key: str          # used as the key in the raw tables
    city: str
    country: str
    latitude: float
    longitude: float
    timezone: str


LOCATIONS: list[Location] = [
    Location("jakarta",      "Jakarta",      "ID", -6.2088,  106.8456, "Asia/Jakarta"),
    Location("singapore",    "Singapore",    "SG",  1.3521,  103.8198, "Asia/Singapore"),
    Location("bangkok",      "Bangkok",      "TH", 13.7563,  100.5018, "Asia/Bangkok"),
    Location("kuala_lumpur", "Kuala Lumpur", "MY",  3.1390,  101.6869, "Asia/Kuala_Lumpur"),
    Location("manila",       "Manila",       "PH", 14.5995,  120.9842, "Asia/Manila"),
    Location("hanoi",        "Hanoi",        "VN", 21.0278,  105.8342, "Asia/Ho_Chi_Minh"),
]

WEATHER_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
]

AIR_QUALITY_VARIABLES = [
    "pm10",
    "pm2_5",
    "carbon_monoxide",
    "nitrogen_dioxide",
    "ozone",
]

# Everything is stored in UTC at the raw layer.
# Conversion to local time happens in the marts layer.
STORAGE_TIMEZONE = "UTC"
