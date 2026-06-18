FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["uvicorn", "wissensdb.main:app", "--host", "0.0.0.0", "--port", "8080"]
