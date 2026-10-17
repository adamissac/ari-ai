# Control-plane developer commands (uv + embedded or Compose PostgreSQL).
.PHONY: install dev-db migrate api worker dev check test contracts smoke stop-db

install:
	uv sync

dev-db:
	@uv run python -m backend.devdb

migrate:
	DATABASE_URL=$${DATABASE_URL:-$$(uv run python -m backend.devdb)} uv run hackatl-migrate

api:
	DATABASE_URL=$${DATABASE_URL:-$$(uv run python -m backend.devdb)} APP_ENV=development AUTH_DEV_LOGIN_ENABLED=true \
	  uv run uvicorn backend.main:app --reload --port 8000

worker:
	DATABASE_URL=$${DATABASE_URL:-$$(uv run python -m backend.devdb)} uv run hackatl-worker

# API + worker against the embedded PostgreSQL (no Docker needed).
dev: migrate
	$(MAKE) -j2 api worker

contracts:
	uv run python -m shared.export
	uv run python -m shared.examples

check:
	uv run ruff check shared monitoring backend
	uv run ruff format --check shared monitoring backend
	uv run python -m shared.export --check
	uv run python -m shared.examples --check

test:
	uv run pytest -q

# Tier 3 live provider smoke: requires ANTHROPIC_API_KEY and explicit opt-in. Costs money.
smoke-live:
	RUN_LIVE_LLM_EVAL=1 uv run pytest -q -m live_llm -s

smoke: check test

stop-db:
	uv run python -m backend.devdb --stop
