from __future__ import annotations

from app.adapters.base import AdapterNotImplemented, CandidateWindow, HealthResult, SourceAdapter


class RtspAdapter(SourceAdapter):
    """RTSP transport adapter — interface defined, implementation pending.

    When built, probe() should attempt an RTSP DESCRIBE/OPTIONS handshake
    (via OpenCV/FFmpeg or aiortc), and discover_candidates() should emit
    rolling live windows from the stream buffer.
    """

    adapter_name = "rtsp"

    def probe(self) -> HealthResult:
        return HealthResult(
            ok=False,
            status="offline",
            error="RTSP adapter not implemented yet",
            details={"unsupported": True},
        )

    def discover_candidates(self) -> list[CandidateWindow]:
        raise AdapterNotImplemented("RTSP ingestion is not implemented yet")
