FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/api

COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN pip install .

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser && mkdir -p /data/storage && chown -R appuser /data
USER appuser

EXPOSE 8000
# Apply migrations, then serve. The migration step needs DATABASE_URL.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000"]
