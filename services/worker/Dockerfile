FROM python:3.11-slim

WORKDIR /app

# ffmpeg is used for evidence clip trimming.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app


# Run as an unprivileged user; writable paths are created and owned up front.
RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin smartops
USER 10001

CMD ["python", "-m", "app.main"]
