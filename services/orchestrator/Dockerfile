FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app


# Run as an unprivileged user; writable paths are created and owned up front.
RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin smartops
USER 10001

EXPOSE 8100

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
