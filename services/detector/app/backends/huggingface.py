"""Opt-in hosted object detection. Quota failures remain inference failures."""
from __future__ import annotations

import math
import re

import httpx

from app.backends.base import DetectorBackend, RawDetection


class HuggingFaceBackend(DetectorBackend):
    name = 'huggingface'

    def __init__(self, token, model='facebook/detr-resnet-50', timeout_seconds=10, *, transport=None):
        if not token:
            raise ValueError('SMARTOPS_HF_TOKEN is required')
        if not re.fullmatch(r'[\w-]+/[\w.-]+', model):
            raise ValueError('Expected a Hugging Face owner/model ID')
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError('Inference timeout must be positive and finite')
        self.token, self.model_name = token, model
        self.timeout_seconds, self.transport = timeout_seconds, transport

    @staticmethod
    def encode(image):
        import cv2

        success, encoded = cv2.imencode('.jpg', image)
        if not success:
            raise ValueError('Could not encode inference image')
        return encoded.tobytes()

    def detect(self, images, min_confidence):
        if not math.isfinite(min_confidence) or not 0 <= min_confidence <= 1:
            raise ValueError('Confidence threshold must be between zero and one')
        results = []
        with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
            for image in images:
                height, width = image.shape[:2]
                if height <= 0 or width <= 0:
                    raise ValueError('Image dimensions must be positive')
                response = client.post(
                    'https://router.huggingface.co/hf-inference/models/' + self.model_name,
                    headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'image/jpeg'},
                    content=self.encode(image))
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, list):
                    raise ValueError('Expected a detection list')
                detections = []
                for item in body:
                    try:
                        label, score, box = item['label'], float(item['score']), item['box']
                        x1, y1, x2, y2 = (float(box[key]) for key in ('xmin', 'ymin', 'xmax', 'ymax'))
                    except (KeyError, TypeError, ValueError) as exc:
                        raise ValueError('Malformed detection') from exc
                    if (not isinstance(label, str) or not label or
                            not all(math.isfinite(v) for v in (score, x1, y1, x2, y2)) or
                            not 0 <= score <= 1 or not 0 <= x1 < x2 <= width or
                            not 0 <= y1 < y2 <= height):
                        raise ValueError('Invalid detection bounds or confidence')
                    if score >= min_confidence:
                        detections.append(RawDetection(label, score, x1 / width, y1 / height,
                                                       (x2 - x1) / width, (y2 - y1) / height))
                results.append(detections)
        return results
