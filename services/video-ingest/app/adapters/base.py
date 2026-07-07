"""Source adapter contract.

Every video input type (MP4 file, RTSP, ONVIF, WebRTC, future custom
gateways) implements this interface so the ingest loop never needs
type-specific branches beyond adapter selection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class AdapterNotImplemented(RuntimeError):
    """Raised by adapters whose transport is not built yet.

    This keeps unsupported source types honest: they surface as explicit
    'adapter pending' health states instead of pretending to ingest.
    """


@dataclass
class HealthResult:
    ok: bool
    status: str  # online | offline | failing
    latency_ms: float | None = None
    error: str | None = None
    adapter: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateWindow:
    """A bounded time window of footage worth analyzing downstream."""

    window_index: int
    start_seconds: float
    end_seconds: float
    signature: str  # stable identity for dedupe (content + window)
    details: dict[str, Any] = field(default_factory=dict)


class SourceAdapter(ABC):
    """Adapter for one registered source (dict as served by /v1/sources)."""

    adapter_name = "base"

    def __init__(self, source: dict) -> None:
        self.source = source

    @abstractmethod
    def probe(self) -> HealthResult:
        """Cheap health check: can the source be opened right now?"""

    @abstractmethod
    def discover_candidates(self) -> list[CandidateWindow]:
        """Enumerate candidate windows for downstream detection."""
