# Build recipe for the sandboxed target (docs/15 §4): non-root, no secrets, no host mounts.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY inventory_lite ./inventory_lite
RUN pip install --no-cache-dir . && useradd --uid 10001 --no-create-home app
USER 10001
EXPOSE 8080
CMD ["uvicorn", "inventory_lite.app:app", "--host", "0.0.0.0", "--port", "8080"]
