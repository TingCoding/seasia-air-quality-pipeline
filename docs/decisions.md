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
