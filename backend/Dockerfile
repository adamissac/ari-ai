# Control-plane image (API and worker share it). Build from the repo root:
#   docker build -f backend/Dockerfile -t hackatl-backend .
FROM python:3.12-slim AS base
# git: connected repositories are fetched at an exact commit (backend/checkouts.py).
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY standards/ standards/
COPY shared/ shared/
COPY monitoring/ monitoring/
COPY backend/ backend/
COPY code-intelligence/ code-intelligence/
COPY code-review/ code-review/
COPY security-agents/ security-agents/
RUN uv sync --frozen --no-dev
# Railway runs API + worker in one service (deploy/railway/start.sh).
COPY --chmod=755 deploy/railway/start.sh /usr/local/bin/railway-start
RUN useradd --create-home --uid 10001 app && mkdir -p /data/artifacts && chown -R app /data
USER app
ENV PATH="/app/.venv/bin:$PATH" ARTIFACT_STORE_URI=file:///data/artifacts
EXPOSE 8000
CMD ["hackatl-api"]
