FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app


# Run as an unprivileged user; writable paths are created and owned up front.
RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin smartops
USER 10001

EXPOSE 8000

# Migrations run inside app startup (app.main.run_migrations) so a plain
# uvicorn command stays valid for local and container runs.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
