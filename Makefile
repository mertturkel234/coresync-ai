.PHONY: help api-install api-run api-test api-lint api-format api-migrate web-install web-dev web-test web-lint web-typecheck test lint infra-up infra-down

PY ?= services/api/.venv/bin/python
ifeq ($(OS),Windows_NT)
PY = services/api/.venv/Scripts/python
endif

help:
	@echo "api-install api-run api-test api-lint api-format api-migrate"
	@echo "web-install web-dev web-test web-lint web-typecheck"
	@echo "test lint infra-up infra-down"

api-install:
	cd services/api && python -m venv .venv && ../../$(PY) -m pip install -e ".[dev]"

api-run:
	cd services/api && ../../$(PY) -m uvicorn app.main:create_app --factory --reload --port 8000

api-test:
	cd services/api && ../../$(PY) -m pytest

api-lint:
	cd services/api && ../../$(PY) -m ruff check . && ../../$(PY) -m ruff format --check .

api-format:
	cd services/api && ../../$(PY) -m ruff format . && ../../$(PY) -m ruff check --fix .

api-migrate:
	cd services/api && ../../$(PY) -m alembic upgrade head

web-install:
	cd apps/web && npm ci

web-dev:
	cd apps/web && npm run dev

web-test:
	cd apps/web && npm test

web-lint:
	cd apps/web && npm run lint

web-typecheck:
	cd apps/web && npm run typecheck

test: api-test web-test

lint: api-lint web-lint web-typecheck

infra-up:
	docker compose up -d postgres redis

infra-down:
	docker compose down
