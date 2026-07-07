from __future__ import annotations

from app.adapters.base import AdapterNotImplemented, CandidateWindow, HealthResult, SourceAdapter


class OnvifAdapter(SourceAdapter):
    """ONVIF adapter — interface defined, implementation pending.

    When built, probe() should run ONVIF device discovery/GetCapabilities and
    resolve the media profile to an RTSP URI, then delegate streaming to the
    RTSP adapter.
    """

    adapter_name = "onvif"

    def probe(self) -> HealthResult:
        return HealthResult(
            ok=False,
            status="offline",
            error="ONVIF adapter not implemented yet",
            details={"unsupported": True},
        )

    def discover_candidates(self) -> list[CandidateWindow]:
        raise AdapterNotImplemented("ONVIF ingestion is not implemented yet")
