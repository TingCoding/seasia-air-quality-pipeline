# Data dictionary

Definitions for every column exposed by the marts layer, including units, source
system, and how each field is derived. Anyone querying this warehouse should be able
to answer "what exactly is this number?" without reading the SQL.

---

## `fct_hourly_measurement`

**Grain.** One row per location × hour × variable × source.

| Column | Type | Description | Source |
|---|---|---|---|
| `measurement_key` | text | Surrogate key: MD5 of location, timestamp, variable and source | Derived |
| `location_key` | text | Foreign key to `dim_location` | Ingestion config |
| `observed_at` | timestamptz | Observation time, always UTC | API |
| `observed_at_local` | timestamp | Local wall-clock time, derived using the city timezone | Derived |
| `date_day` | date | Calendar day in UTC, foreign key to `dim_date` | Derived |
| `hour_utc` | int | Hour of day, 0–23, in UTC | Derived |
| `variable_name` | text | Measured variable, see the variable reference below | API |
| `measurement_domain` | text | `weather` or `air_quality` | Derived |
| `measurement_value` | double | The measurement. NULL when the source reports no value | API |
| `measurement_unit` | text | Unit as reported by the source | API |
| `source_system` | text | Which API endpoint produced this row | Ingestion |
| `is_missing` | boolean | True when `measurement_value` is NULL | Derived |
| `ingested_at` | timestamptz | When this row was last written | Ingestion |

## `dim_location`

**Grain.** One row per city.

| Column | Type | Description |
|---|---|---|
| `location_key` | text | Primary key, lower-case city identifier |
| `city` | text | Display name |
| `country_code` | text | ISO 3166-1 alpha-2 |
| `country` | text | Country name |
| `latitude` | double | Decimal degrees, north positive |
| `longitude` | double | Decimal degrees, east positive |
| `timezone` | text | IANA timezone name, used to derive local time |
| `has_measurements` | boolean | Whether any data has actually been collected for this city |

## `dim_date`

**Grain.** One row per calendar day, spanning the range of data present.

| Column | Type | Description |
|---|---|---|
| `date_day` | date | Primary key |
| `year`, `quarter`, `month` | int | Calendar parts |
| `month_name`, `day_name` | text | Padded names as returned by `to_char` |
| `day_of_month` | int | 1–31 |
| `day_of_week` | int | ISO weekday, 1 = Monday through 7 = Sunday |
| `is_weekend` | boolean | True for Saturday and Sunday |

## `agg_daily_air_quality`

**Grain.** One row per city × day × pollutant.

| Column | Type | Description |
|---|---|---|
| `location_key` | text | Foreign key to `dim_location` |
| `date_day` | date | Calendar day in UTC |
| `variable_name` | text | Pollutant |
| `measurement_unit` | text | Unit as reported by the source |
| `avg_value`, `min_value`, `max_value` | numeric | Daily statistics, rounded to 2 decimals |
| `expected_hours` | int | Hours present in the fact table for this day |
| `observed_hours` | int | Hours that actually carry a value |
| `measurement_completeness_pct` | numeric | `observed_hours / expected_hours`, as a percentage |

**Read `measurement_completeness_pct` before trusting `avg_value`.** An average backed
by three hours of data is not comparable to one backed by twenty-four.

---

## Variable reference

### Weather — source: Open-Meteo Archive API

| Variable | Unit | Description |
|---|---|---|
| `temperature_2m` | °C | Air temperature 2 metres above ground |
| `relative_humidity_2m` | % | Relative humidity 2 metres above ground |
| `precipitation` | mm | Total precipitation for the hour |
| `wind_speed_10m` | km/h | Wind speed 10 metres above ground |
| `wind_direction_10m` | ° | Wind direction, 0 = north, clockwise |

### Air quality — source: Open-Meteo Air Quality API

| Variable | Unit | Description |
|---|---|---|
| `pm2_5` | µg/m³ | Particulate matter under 2.5 micrometres |
| `pm10` | µg/m³ | Particulate matter under 10 micrometres |
| `carbon_monoxide` | µg/m³ | CO concentration |
| `nitrogen_dioxide` | µg/m³ | NO₂ concentration |
| `ozone` | µg/m³ | O₃ concentration |

Units are recorded per row in `measurement_unit` rather than assumed. If a source ever
changes units, the change is visible in the data instead of silently corrupting it.

---

## Audit

### `audit.data_quality_log`

Every dbt test outcome is appended here by the `log_dbt_results` macro on each run.

| Column | Type | Description |
|---|---|---|
| `id` | bigserial | Primary key |
| `checked_at` | timestamptz | When the test ran |
| `check_name` | text | Test name as defined in dbt |
| `target_table` | text | Node the test was attached to |
| `status` | text | `pass`, `fail`, `warn`, or `error` |
| `failed_rows` | bigint | Number of rows that violated the test |
| `detail` | text | Message returned by dbt, truncated to 500 characters |

Useful query — which checks have failed most often:

```sql
SELECT check_name,
       count(*) FILTER (WHERE status <> 'pass') AS failures,
       count(*)                                 AS runs,
       max(checked_at)                          AS last_run
FROM audit.data_quality_log
GROUP BY check_name
HAVING count(*) FILTER (WHERE status <> 'pass') > 0
ORDER BY failures DESC;
```
