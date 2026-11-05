FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app


# Run as an unprivileged user; writable paths are created and owned up front.
RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin smartops \
    && mkdir -p /data && chown smartops /data
USER 10001

CMD ["python", "-m", "app.main"]
