"""Detector backend registry.

The active backend is selected with SMARTOPS_DETECTOR_BACKEND:
  ultralytics-cpu   local YOLO on CPU (default)
  ultralytics-cuda  local YOLO on an NVIDIA GPU (CUDA torch build)
  remote            another SmartOps detector API, e.g. a GPU box
  huggingface       hosted Hugging Face object detection (opt-in)
"""

from __future__ import annotations

import os

from app.backends.base import DetectorBackend

PLANNED_BACKENDS = ("onnxruntime", "openvino")


def get_backend() -> DetectorBackend:
    name = os.getenv("SMARTOPS_DETECTOR_BACKEND", "ultralytics-cpu")
    if name == 'huggingface':
        from app.backends.huggingface import HuggingFaceBackend

        return HuggingFaceBackend(os.getenv('SMARTOPS_HF_TOKEN', ''),
                                 os.getenv('SMARTOPS_HF_MODEL', 'facebook/detr-resnet-50'),
                                 float(os.getenv('SMARTOPS_HF_TIMEOUT_SECONDS', '10')))
    if name == "ultralytics-cpu":
        from app.backends.ultralytics_cpu import UltralyticsCpuBackend

        return UltralyticsCpuBackend()
    if name == "ultralytics-cuda":
        from app.backends.ultralytics_cpu import UltralyticsCudaBackend

        return UltralyticsCudaBackend()
    if name == "remote":
        from app.backends.remote import RemoteBackend

        return RemoteBackend(os.getenv("SMARTOPS_DETECTOR_REMOTE_URL", ""),
                             os.getenv("SMARTOPS_DETECTOR_REMOTE_TOKEN", ""),
                             float(os.getenv("SMARTOPS_DETECTOR_REMOTE_TIMEOUT_SECONDS", "5")))
    if name in PLANNED_BACKENDS:
        raise RuntimeError(
            f"Detector backend '{name}' is planned but not implemented yet. "
            "Use 'ultralytics-cpu' or implement the backend in app/backends/."
        )
    raise RuntimeError(f"Unknown detector backend '{name}'.")
