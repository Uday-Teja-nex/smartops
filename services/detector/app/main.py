"""SmartOps detector service.

Runs lightweight YOLO object detection on sampled frames so expensive
VLM/LLM review only happens on candidate windows that show something. The
inference backend is pluggable (SMARTOPS_DETECTOR_BACKEND); CPU ultralytics
is the local default.
"""

from __future__ import annotations

import base64
import time

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.backends import get_backend

app = FastAPI(title="SmartOps Detector", version="0.1.0")
backend = get_backend()


class FramePayload(BaseModel):
    frameIndex: int
    timestampSeconds: float
    imageBase64: str


class DetectRequest(BaseModel):
    frames: list[FramePayload]
    minConfidence: float = Field(default=0.35, ge=0, le=1)


class DetectionBoxPayload(BaseModel):
    x: float
    y: float
    w: float
    h: float


class DetectionPayload(BaseModel):
    frameIndex: int
    timestampSeconds: float
    label: str
    confidence: float
    bbox: DetectionBoxPayload


class DetectResponse(BaseModel):
    modelName: str
    backend: str
    inferenceMs: float
    detections: list[DetectionPayload]


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "detector",
        "backend": backend.name,
        "model": backend.model_name,
    }


@app.post("/v1/detect", response_model=DetectResponse)
def detect(payload: DetectRequest) -> DetectResponse:
    if not payload.frames:
        return DetectResponse(
            modelName=backend.model_name, backend=backend.name, inferenceMs=0, detections=[]
        )

    images = []
    for frame in payload.frames:
        try:
            raw = base64.b64decode(frame.imageBase64)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"invalid base64 frame: {exc}") from exc
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(status_code=422, detail="frame could not be decoded as an image")
        images.append(image)

    started = time.perf_counter()
    per_frame = backend.detect(images, payload.minConfidence)
    elapsed_ms = (time.perf_counter() - started) * 1000

    detections: list[DetectionPayload] = []
    for frame, frame_detections in zip(payload.frames, per_frame):
        for det in frame_detections:
            detections.append(
                DetectionPayload(
                    frameIndex=frame.frameIndex,
                    timestampSeconds=frame.timestampSeconds,
                    label=det.label,
                    confidence=round(det.confidence, 4),
                    bbox=DetectionBoxPayload(
                        x=round(det.x, 4),
                        y=round(det.y, 4),
                        w=round(det.w, 4),
                        h=round(det.h, 4),
                    ),
                )
            )

    return DetectResponse(
        modelName=backend.model_name,
        backend=backend.name,
        inferenceMs=round(elapsed_ms, 1),
        detections=detections,
    )
