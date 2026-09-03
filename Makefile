.PHONY: help up down logs migrate seed test test-backend test-frontend build demo install-backend install-frontend

help:
	@echo "MLR RuleOps"
	@echo "  make up              docker compose up --build"
	@echo "  make down            docker compose down"
	@echo "  make migrate         alembic upgrade head"
	@echo "  make seed            seed demo data"
	@echo "  make test            backend + frontend tests"
	@echo "  make demo            process seeded demo ticket via API"

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f backend worker

migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && python -m app.db.seed

generate-reviews:
	python scripts/generate_demo_data.py --reviews 2000

install-backend:
	cd backend && python -m pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

test-backend:
	cd backend && python -m pytest -q

test-frontend:
	cd frontend && npm test -- --run

test: test-backend test-frontend

build:
	cd frontend && npm run build

demo:
	bash scripts/demo_walkthrough.sh
