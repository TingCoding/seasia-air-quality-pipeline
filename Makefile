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
