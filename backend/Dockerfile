FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/src /app/src
COPY games /app/games

RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
