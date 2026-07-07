from __future__ import annotations

from app.adapters.base import AdapterNotImplemented, CandidateWindow, HealthResult, SourceAdapter


class WebRtcAdapter(SourceAdapter):
    """WebRTC adapter — interface defined, implementation pending.

    When built, probe() should validate the signaling endpoint and
    discover_candidates() should emit windows from the received track buffer
    (aiortc or an external gateway).
    """

    adapter_name = "webrtc"

    def probe(self) -> HealthResult:
        return HealthResult(
            ok=False,
            status="offline",
            error="WebRTC adapter not implemented yet",
            details={"unsupported": True},
        )

    def discover_candidates(self) -> list[CandidateWindow]:
        raise AdapterNotImplemented("WebRTC ingestion is not implemented yet")
