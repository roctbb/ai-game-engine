FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/src /app/src
COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
COPY backend/entrypoint.sh /app/entrypoint.sh
COPY games /app/games

RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["/app/entrypoint.sh"]
