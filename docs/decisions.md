# Decision log

Technical decisions taken during development, with the reasoning behind them.
Format: decision, context, why, consequences.

---

## 1. Raw data is stored verbatim

**Decision.** API responses are written to the `raw` schema with no transformation.

**Why.** If transformation logic turns out to be wrong, the warehouse can be rebuilt
without calling the APIs again. It also draws a clean boundary of responsibility:
ingestion moves data, dbt reshapes it.

**Consequences.** More storage, and one extra layer to maintain.

---

## 2. All timestamps are stored in UTC

**Decision.** `observed_at` is `TIMESTAMPTZ` and always UTC. Conversion to local time
happens in the marts layer.

**Why.** The six cities span four timezones. Storing local time makes cross-city
comparison error-prone, particularly when aggregating by hour.

**Consequences.** Per-city daily analysis needs an explicit conversion.

---

## 3. Composite primary key at the raw layer, not a surrogate key

**Decision.** `(location_key, observed_at, variable, source)` as the primary key.

**Why.** It makes loading idempotent — re-running ingestion for the same date range
does not duplicate rows. This matters because API calls do fail halfway and have to be
retried.

**Consequences.** Writes must use `ON CONFLICT DO UPDATE`, marginally slower than a
plain `INSERT`.

---

## 4. Data is stored in long format, not wide

**Decision.** The fact table holds one row per variable
(`location x hour x variable x source`) rather than one column per variable.

**Why.** The list of variables will grow. A wide format forces a schema migration
every time a new pollutant or weather variable is added; long format only adds rows.

**Consequences.** Comparing variables side by side requires a pivot, and row counts are
much higher. For everyday analysis this is handled by `agg_daily_air_quality`.

---

## 5. Completeness is reported, not hidden

**Decision.** `agg_daily_air_quality` carries a `measurement_completeness_pct` column.

**Why.** A daily average computed from three hours of data is not the same as one
computed from twenty-four. Presenting both as a single unlabelled number would mislead
whoever consumes the data.

**Consequences.** Consumers have to decide for themselves what completeness threshold
is acceptable.

---

## 6. Local time is derived in the marts layer

**Decision.** `observed_at_local` is computed in `fct_hourly_measurement` using the
timezone from `dim_location`, rather than stored from the raw layer.

**Why.** The raw layer should stay neutral and lose no information. Timezone is a
presentation decision, not a fact about the measurement.

**Consequences.** Correcting a city's timezone means fixing the seed, not reloading
data from the API.

---

## 7. Dependency versions are pinned exactly

**Decision.** `dbt-core==1.11.14` and `dbt-postgres==1.11.0`, not `dbt-postgres>=1.8,<2.0`.

**Why.** Two real problems surfaced with a loose range. First, `dbt-postgres` declares
its requirement as `dbt-core<2.0,>=1.8.0rc1`; because the lower bound is a pre-release,
pip considered pre-releases eligible and installed the dbt 2.0 beta, which does not
support PostgreSQL. Second, `dbt-core` 1.12 added a dependency that downloads a large
binary at install time, making installation fragile on an unstable connection.

**Consequences.** Upgrades have to be deliberate rather than automatic. That is the
point: a repository that works today should still work next month without a single
line of code changing.

---

## 8. Service ports are configurable, not hardcoded

**Decision.** Ports in `docker-compose.yml` read from environment variables with
defaults, for example `${ADMINER_PORT:-8081}`.

**Why.** Port 8080 was already occupied on the development machine by an unrelated
service. A repository with hardcoded ports fails on someone else's machine for reasons
that have nothing to do with the code, and a reviewer who cannot start it will simply
stop there.

**Consequences.** One more variable to document in `.env.example`.

---

## 9. Test results are persisted, not just printed

**Decision.** An `on-run-end` macro writes every dbt test outcome into
`audit.data_quality_log`.

**Why.** Test results that exist only in terminal output disappear when the window
closes. Stored in a table, data quality becomes queryable over time: which check fails
most often, whether a failure is new or long-standing, and whether a fix actually held.
A single red run tells you something is wrong; a history tells you what is wrong.

**Consequences.** The audit table grows with every run and will eventually need a
retention policy.

---

## 10. Source-driven failures are warnings, not errors

**Decision.** `assert_no_long_data_gaps` and `assert_daily_completeness_is_plausible`
run at `warn` severity; everything else fails the build.

**Why.** A gap in the upstream feed is not a defect in this pipeline. Treating it as a
build failure trains whoever maintains this to ignore red runs, which is worse than
having no test at all. Errors are reserved for conditions that indicate something here
is broken — impossible values, duplicate rows, broken referential integrity.

**Consequences.** Warnings can be overlooked if nobody reads the run summary. The audit
table in decision 9 is the mitigation.

---

## 11. OpenAQ station selection follows written rules

**Decision.** Stations enter the warehouse only if they expose a wanted parameter,
have reported within 90 days, and are not mobile. Of those that qualify, the five
most recently active per city are kept. The thresholds live in `ingestion/config.py`.

**Why.** A survey of the six cities found 27 registered stations around Jakarta of
which only 2 still report, and over 100 around Bangkok of which roughly 80 report
daily. Several entries are abandoned test uploads — one provider's Singapore listings
include stations named `hhhhhhhh`, `try 2` and `t`, none with any data. Choosing
stations by eye would be unrepeatable and impossible to defend later; encoding the
criteria makes the selection auditable and identical for every city.

**Consequences.** A genuinely useful station that has been quiet for 91 days is
excluded. The threshold is a judgement call and is deliberately easy to change.

---

## 12. Only µg/m³ parameters are ingested for now

**Decision.** OpenAQ ingestion is limited to `pm25` and `pm10`.

**Why.** Gases are reported inconsistently across networks: Air4Thai sends CO, NO₂,
O₃ and SO₂ in ppm, while Hanoi Air Quality sends the same pollutants in µg/m³. One
Bangkok station reports CO in ppm *and* ppb simultaneously, and a Jakarta station
reports temperature in both Fahrenheit and Celsius. Loading these without explicit
conversion would produce numbers that look plausible and are wrong by orders of
magnitude. PM2.5 and PM10 arrive in µg/m³ from every provider observed.

**Consequences.** Four pollutants available from OpenAQ are left on the table until
unit conversion is implemented as a first-class step rather than an afterthought.

---

## 13. Duplicate sensors are preserved, not resolved at ingestion

**Decision.** When a station exposes two sensors for the same parameter, both are
loaded.

**Why.** Deciding which of two co-located sensors to trust is an analytical question,
not an ingestion one. Silently dropping one at load time would hide the duplication
from the layer built to detect it, and would be irreversible without a reload.

**Consequences.** Anything aggregating across sensors must group by sensor first, or
a station with two PM2.5 sensors will be double-counted.

---

## 14. OpenAQ tables are separate from Open-Meteo tables

**Decision.** OpenAQ writes to `raw.openaq_*` rather than into the shared
`raw.air_quality_hourly`.

**Why.** OpenAQ measurements attach to identifiable physical stations, each with an
operator, an instrument, a lifespan and a coverage figure per hourly average.
Open-Meteo values are modelled at a coordinate and carry none of that. Forcing both
into one table would mean discarding the metadata that makes station data worth
having in the first place. The two are reconciled in dbt, where the join is explicit
and visible.

**Consequences.** One more set of tables, and the union happens later in the stack.

---

## 15. Station selection is pinned to a file, not re-derived per run (revises 11)

**Decision.** `--discover` proposes stations and writes them to
`dbt/seeds/openaq_stations.csv`. A normal run reads that file and loads exactly
those stations. Decision 11 described the selection rules; this decision changes
when they are applied.

**Why.** The rules in decision 11 were applied on every run, and one of them ranks
stations by how recently they reported. Because that value advances continuously, two
runs thirteen hours apart selected entirely different stations for Bangkok — the same
command, a different result, and a warehouse holding a blend nobody could account for.
Reproducibility is not a property that can be added later; a pipeline that cannot be
re-run to the same outcome cannot be trusted or debugged.

Rules still decide *what qualifies*. A human decides *what is used*, once, and the
answer is committed to version control where it can be reviewed and its history read.

**Consequences.** Adding a station is now a deliberate act with a commit behind it. A
station that goes dark stays in the registry until someone removes it — which is why
the loader logs a warning when a pinned station is no longer returned, rather than
skipping it silently.

---

## 16. Time windows are sent to OpenAQ as explicit UTC

**Decision.** `datetime_from` and `datetime_to` are sent as full UTC datetimes rather
than bare dates.

**Why.** OpenAQ interprets a bare date in the station's local time. A request for
2025-01-01 in Bangkok returned rows beginning 2024-12-31T17:00Z — the UTC+7 offset. The
window therefore shifted by a different amount in every city, which would have made
cross-city comparison quietly wrong. This was found by reading the `min(observed_at)`
of loaded data rather than by reading the documentation, which is the usual way such
things are found.

**Consequences.** `--end` is now inclusive of the whole UTC day. Data loaded before this
change is offset by the city's UTC offset and should be reloaded.

---

## 17. The station registry doubles as a dbt seed

**Decision.** The registry lives at `dbt/seeds/openaq_stations.csv`, serving both as the
input to ingestion and as the seed behind the station dimension.

**Why.** One file, one truth. It also makes a useful comparison trivial: the registry
records what was selected and when, while `raw.openaq_stations` records what the API
reports now. Asking whether a chosen station has since gone quiet becomes a query
rather than an investigation.

**Consequences.** A file with two consumers needs care — changing its columns affects
both ingestion and the dbt models.

---

## 18. Seed column types are declared, not inferred

**Decision.** `dbt_project.yml` declares the column types for the station registry seed,
and the registry reader accepts several date formats.

**Why.** The registry is deliberately a file people edit by hand. Opening it in a
spreadsheet application and saving rewrites `2026-08-28` as `28/08/2026` and `True` as
`TRUE`, which broke the seed load with a datestyle error. The choice was to forbid that
workflow or to tolerate it; tolerating it is better, because a file meant for human
review will be opened by humans using whatever tool they have. Declaring the types also
makes the load independent of the database's `datestyle` setting, which differs between
installations.

**Consequences.** Timestamp columns arrive as text and are cast downstream in dbt, where
the conversion is visible rather than implicit.

---

## 19. Measured and modelled values live in separate fact tables

**Decision.** `fct_station_measurement` holds OpenAQ station readings;
`fct_hourly_measurement` holds Open-Meteo modelled values. They are compared in
`agg_daily_pm25_comparison`, not merged.

**Why.** A reanalysis model and a physical instrument answer different questions and
carry different uncertainty. Placing them in one table with a `source` column would let
a reader average across both without noticing, producing a figure that means nothing.
Separation makes the comparison an explicit act.

**Consequences.** Anyone wanting both must join, which is the intended friction.

---

## 20. Completeness for OpenAQ is measured against expected hours, not NULLs

**Decision.** `agg_daily_station_coverage` compares observed hours against the 24 a full
day should contain.

**Why.** The two sources express absence differently. Open-Meteo returns every hour and
sets the value to NULL when it has none; OpenAQ omits the row entirely. The NULL-based
checks written for the first source therefore find nothing in the second, and a sensor
that stopped reporting would pass every test while producing no data. Loading revealed
this directly: `count(*)` and `count(value)` were identical for every OpenAQ series, yet
one Jakarta series held only a third of the hours in its window.

**Consequences.** Two different completeness measures exist in the warehouse. Their
column names say which is which.

---

## 21. Provider class is surfaced, not resolved

**Decision.** `dim_station.station_class` marks each station as `reference` or
`low_cost`. No station is excluded on that basis.

**Why.** OpenAQ presents a government reference monitor and a community sensor under one
schema, but they do not carry equal weight. Dropping the low-cost sensors would discard
most of the coverage in several cities; treating them as equivalent would overstate
precision. Labelling lets whoever queries the warehouse decide, which is where the
decision belongs.

**Consequences.** Any analysis that ignores `station_class` is mixing instrument grades
without saying so.

---

## 22. Casts from the registry are guarded, not direct

**Decision.** `stg_openaq_registry` checks a value's shape with a pattern before casting
it, and records `has_unparseable_dates` when a non-empty cell fails to parse.

**Why.** A direct `::timestamptz` on a hand-editable file fails the entire build on a
single empty cell — which is exactly what happened. The registry is meant to be reviewed
and corrected by people, so its contents cannot be assumed well-formed. Turning a bad
value into NULL and flagging it lets the tests report the problem, instead of one stray
space stopping every downstream model.

**Consequences.** A malformed date becomes NULL, so anything depending on those columns
must handle NULL. The flag column exists so the fault is still visible.
