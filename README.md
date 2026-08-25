# Southeast Asia Air Quality Data Pipeline

An end-to-end ELT pipeline that ingests hourly air quality and weather data for
six Southeast Asian cities from public APIs into PostgreSQL, transforms it with
dbt, and validates it with automated data quality checks.

> **Status:** work in progress — Stage 0 (foundation) complete.

---

## Architecture

<!-- TODO: ganti dengan docs/architecture.png setelah Tahap 2 -->
```
Open-Meteo API  ─┐
                 ├─> ingestion (Python) ─> raw schema ─> dbt ─> marts ─> analysis
OpenAQ API      ─┘                          (PostgreSQL)
```

## Data sources

| Source | Data | API key |
|---|---|---|
| [Open-Meteo](https://open-meteo.com/) | Hourly weather and air quality, reanalysis-based | Not required |
| [OpenAQ v3](https://docs.openaq.org/) | Ground station measurements | Free, required |

## Quick start

```bash
git clone https://github.com/<username>/seasia-air-quality-pipeline.git
cd seasia-air-quality-pipeline
cp .env.example .env          # sesuaikan password
docker compose up -d
```

Database siap saat `docker compose ps` menunjukkan status `healthy`.
Antarmuka SQL tersedia di http://localhost:8080 (Adminer), server `postgres`.

Verifikasi skema:

```bash
docker compose exec postgres psql -U aq_user -d air_quality -c "\dn"
```

## Project structure

```
ingestion/     klien API dan pemuatan ke lapisan raw
dbt/           model transformasi: staging -> intermediate -> marts
sql/ddl/       skema awal, dijalankan otomatis saat container dibuat
tests/         pytest untuk logika ingestion
docs/          kamus data, diagram, catatan keputusan teknis
```

## Data model

<!-- TODO: isi setelah Tahap 2 -->

## Data quality checks

<!-- TODO: isi setelah Tahap 3 -->

## Technical decisions

Lihat [docs/decisions.md](docs/decisions.md).

## Limitations and next steps

<!-- TODO: isi jujur di akhir -->

## License

MIT
