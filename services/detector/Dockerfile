FROM python:3.11-slim

WORKDIR /app

# libgl/glib are required by opencv; kept minimal for CPU inference.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# CPU-only torch by default so ultralytics does not pull the CUDA build.
# GPU hosts: --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 \
    --index-url ${TORCH_INDEX_URL}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the default model weights into the image so first start is offline-safe.
ENV YOLO_CONFIG_DIR=/app/.ultralytics
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

COPY app ./app


# Run as an unprivileged user; writable paths are created and owned up front.
RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin smartops \
    && chown -R smartops /app/.ultralytics
USER 10001

EXPOSE 8200

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8200"]
