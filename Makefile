.PHONY: up down logs psql init reset test lint

up:            ## start the database
	docker compose up -d

down:          ## stop, keeping data
	docker compose down

reset:         ## stop and delete all data (destructive)
	docker compose down -v

logs:
	docker compose logs -f postgres

psql:          ## open a SQL shell
	docker compose exec postgres psql -U aq_user -d air_quality

test:
	pytest -q

lint:
	ruff check .

# ---------- dbt ----------
seed:
	cd dbt && dbt seed

build:          ## seed, run and test in one go
	cd dbt && dbt build

dbt-docs:
	cd dbt && dbt docs generate && dbt docs serve

# ---------- OpenAQ ----------
openaq-schema:  ## apply the OpenAQ tables to a running database
	docker compose exec -T postgres psql -U aq_user -d air_quality \
		-f /docker-entrypoint-initdb.d/002_openaq.sql

openaq-discover: ## propose a station list and write it to the registry
	python -m ingestion.run_openaq --discover
