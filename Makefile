.PHONY: up down logs psql init reset test lint

up:            ## nyalakan database
	docker compose up -d

down:          ## matikan, data tetap tersimpan
	docker compose down

reset:         ## matikan dan hapus data (hati-hati)
	docker compose down -v

logs:
	docker compose logs -f postgres

psql:          ## masuk ke shell SQL
	docker compose exec postgres psql -U aq_user -d air_quality

test:
	pytest -q

lint:
	ruff check .

# ---------- dbt ----------
seed:
	cd dbt && dbt seed

build:          ## seed + run + test sekaligus
	cd dbt && dbt build

dbt-docs:
	cd dbt && dbt docs generate && dbt docs serve
