from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ModelLoading(Exception):
    """The model is not in memory yet; a background load has been started."""


class ModelBusy(Exception):
    """The local model stayed busy with other reviews past the queue limit."""


class ModelProvider(ABC):
    @abstractmethod
    def review_event_evidence_base64(self, prompt: str, images: list[str], schema: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def review_event_evidence(
        self,
        prompt: str,
        image_paths: list[Path],
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def summarize_incident(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def suggest_actions(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError
