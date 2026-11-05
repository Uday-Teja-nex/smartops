"""Forward detection to another SmartOps detector API (e.g. a GPU inference box).

The remote side runs this same service with a local backend, so the request
and response contract is unchanged. Frames are re-encoded as JPEG.
"""
from __future__ import annotations

import base64
from typing import Any

import cv2
import httpx

from app.backends.base import DetectorBackend, RawDetection


class RemoteBackend(DetectorBackend):
    name = "remote"

    def __init__(self, url: str, token: str = "", timeout_seconds: float = 5.0,
                 client: httpx.Client | None = None) -> None:
        if not url.startswith(("http://", "https://")):
            raise ValueError("SMARTOPS_DETECTOR_REMOTE_URL must be an http(s) URL")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.client = client or httpx.Client(base_url=url.rstrip("/"), timeout=timeout_seconds, headers=headers)
        self.model_name = "remote"

    def detect(self, images: list[Any], min_confidence: float) -> list[list[RawDetection]]:
        if not images:
            return []
        frames = []
        for index, image in enumerate(images):
            ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                raise ValueError("Frame could not be encoded for the remote detector")
            frames.append({"frameIndex": index, "timestampSeconds": 0.0,
                           "imageBase64": base64.b64encode(encoded).decode("ascii")})
        response = self.client.post("/v1/detect", json={"minConfidence": min_confidence, "frames": frames})
        response.raise_for_status()
        body = response.json()
        self.model_name = f"remote:{body.get('modelName', 'unknown')}"
        outputs: list[list[RawDetection]] = [[] for _ in images]
        for item in body.get("detections", []):
            index = int(item["frameIndex"])
            if not 0 <= index < len(images):
                raise ValueError("Remote detector returned an unknown frame index")
            box = item["bbox"]
            outputs[index].append(RawDetection(label=str(item["label"]), confidence=float(item["confidence"]),
                                               x=float(box["x"]), y=float(box["y"]),
                                               w=float(box["w"]), h=float(box["h"])))
        return outputs
