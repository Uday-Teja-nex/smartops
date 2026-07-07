FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

EXPOSE 8000

# Migrations run inside app startup (app.main.run_migrations) so a plain
# uvicorn command stays valid for local and container runs.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
