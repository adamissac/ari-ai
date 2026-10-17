FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir "fastapi==0.143.3" "uvicorn==0.54.0" "pydantic==2.14.1"
WORKDIR /app
COPY payments_lite /app/payments_lite
CMD ["python", "-m", "uvicorn", "--factory", "payments_lite.app:create_app", "--host", "0.0.0.0", "--port", "8000"]
