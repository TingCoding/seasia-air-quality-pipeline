"""Konfigurasi terpusat: daftar lokasi dan parameter yang diambil.

Daftar kota sengaja dipisahkan ke sini agar cakupan project bisa diubah
tanpa menyentuh kode ingestion. Sesuaikan setelah mengecek ketersediaan
stasiun OpenAQ di tiap kota.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    key: str          # dipakai sebagai kunci di tabel raw
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

# Semua waktu diseragamkan ke UTC di lapisan raw.
# Konversi ke waktu lokal dilakukan di lapisan marts.
STORAGE_TIMEZONE = "UTC"
