from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ModelProvider(ABC):
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
