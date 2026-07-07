from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class RawDetection:
    label: str
    confidence: float
    # Normalized [0,1] coordinates relative to the frame.
    x: float
    y: float
    w: float
    h: float


class DetectorBackend(ABC):
    """One inference backend (CPU ultralytics now; ONNX/OpenVINO/CUDA/remote later)."""

    name: str = "base"
    model_name: str = "unknown"

    @abstractmethod
    def detect(self, images: list[Any], min_confidence: float) -> list[list[RawDetection]]:
        """Run detection on decoded BGR images; one result list per image."""
