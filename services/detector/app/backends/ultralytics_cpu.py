from __future__ import annotations

import os
from threading import Lock
from typing import Any

import torch
from ultralytics import YOLO

from app.backends.base import DetectorBackend, RawDetection

MODEL_PATH = os.getenv("SMARTOPS_YOLO_MODEL", "yolov8n.pt")


class UltralyticsCpuBackend(DetectorBackend):
    name = "ultralytics-cpu"

    def __init__(self) -> None:
        threads = int(os.getenv('SMARTOPS_DETECTOR_CPU_THREADS', '2'))
        if not 1 <= threads <= 16:
            raise ValueError('SMARTOPS_DETECTOR_CPU_THREADS must be between 1 and 16')
        torch.set_num_threads(threads)
        # A torch.device preserves our budget in Ultralytics select_device;
        # the string "cpu" resets it to the library's eight-thread default.
        self.device = torch.device('cpu')
        self.image_size = int(os.getenv('SMARTOPS_DETECTOR_IMAGE_SIZE', '640'))
        if not 320 <= self.image_size <= 1280 or self.image_size % 32:
            raise ValueError('SMARTOPS_DETECTOR_IMAGE_SIZE must be a multiple of 32 between 320 and 1280')
        self.lock = Lock()
        self.model = YOLO(MODEL_PATH)
        self.model_name = os.path.basename(MODEL_PATH)

    def detect(self, images: list[Any], min_confidence: float) -> list[list[RawDetection]]:
        if not images:
            return []
        with self.lock:
            results = self.model.predict(
                images,
                conf=min_confidence,
                device=self.device,
                imgsz=self.image_size,
                verbose=False,
            )
        outputs: list[list[RawDetection]] = []
        for result in results:
            frame_detections: list[RawDetection] = []
            names = result.names
            boxes = result.boxes
            if boxes is not None:
                height, width = result.orig_shape
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    frame_detections.append(
                        RawDetection(
                            label=str(names[int(box.cls[0])]),
                            confidence=float(box.conf[0]),
                            x=max(0.0, x1 / width),
                            y=max(0.0, y1 / height),
                            w=min(1.0, (x2 - x1) / width),
                            h=min(1.0, (y2 - y1) / height),
                        )
                    )
            outputs.append(frame_detections)
        return outputs
