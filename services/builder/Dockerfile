FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY services/builder/pyproject.toml /app/pyproject.toml
COPY services/builder/src /app/src

RUN pip install --no-cache-dir .

EXPOSE 8030
CMD ["uvicorn", "builder_service.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8030"]
