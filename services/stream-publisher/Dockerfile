FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY publish.py .
RUN mkdir /cache && chown nobody:nogroup /cache
USER nobody
CMD ["python", "publish.py"]
