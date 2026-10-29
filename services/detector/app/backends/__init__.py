"""Detector backend registry.

The active backend is selected with SMARTOPS_DETECTOR_BACKEND. Only the
CPU ultralytics and opt-in Hugging Face backends are implemented; the registry names the planned
alternatives so switching later is configuration, not a rewrite.
"""

from __future__ import annotations

import os

from app.backends.base import DetectorBackend

PLANNED_BACKENDS = ("onnxruntime", "openvino", "cuda", "remote")


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
    if name in PLANNED_BACKENDS:
        raise RuntimeError(
            f"Detector backend '{name}' is planned but not implemented yet. "
            "Use 'ultralytics-cpu' or implement the backend in app/backends/."
        )
    raise RuntimeError(f"Unknown detector backend '{name}'.")
