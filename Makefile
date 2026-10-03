.PHONY: install db migrate seed demo api web dev test lint e2e gen-api up down

CHROMIUM_PATH ?= $(shell ls -d /opt/pw-browsers/chromium-*/chrome-linux*/chrome 2>/dev/null | head -1)

install:            ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && npm install

db:                 ## Start only Postgres in Docker
	docker compose up -d db

migrate:            ## Apply database migrations
	cd backend && uv run alembic upgrade head

seed:               ## Create the admin user, store settings and GST rates
	cd backend && uv run python -m app.seed

demo:               ## Seed plus a demo catalog, stock and 30 days of sales
	cd backend && uv run python -m app.seed --demo

api:                ## Run the API with reload on :8000
	cd backend && uv run uvicorn app.main:app --reload --port 8000

web:                ## Run the Next.js dev server on :3000
	cd frontend && npm run dev

dev:                ## Run API and web together
	$(MAKE) -j2 api web

test:               ## Backend tests (needs Postgres with an ims_test database)
	cd backend && uv run pytest -q

lint:               ## Lint and type-check both apps
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint && npm run typecheck

e2e:                ## Browser tests against a running API (demo data) and web app
	cd frontend && CHROMIUM_PATH=$(CHROMIUM_PATH) npx playwright test

gen-api:            ## Regenerate the frontend's typed API client from FastAPI's OpenAPI
	cd frontend && npm run gen:api

up:                 ## Build and run everything in Docker
	docker compose up --build

down:
	docker compose down
