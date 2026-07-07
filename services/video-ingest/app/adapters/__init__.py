from app.adapters.base import (
    AdapterNotImplemented,
    CandidateWindow,
    HealthResult,
    SourceAdapter,
)
from app.adapters.mp4 import Mp4FileAdapter
from app.adapters.onvif import OnvifAdapter
from app.adapters.rtsp import RtspAdapter
from app.adapters.webrtc import WebRtcAdapter

ADAPTERS_BY_TYPE: dict[str, type[SourceAdapter]] = {
    "file": Mp4FileAdapter,
    "rtsp": RtspAdapter,
    "onvif": OnvifAdapter,
    "webrtc": WebRtcAdapter,
}


def get_adapter(source: dict) -> SourceAdapter:
    adapter_cls = ADAPTERS_BY_TYPE.get(source.get("sourceType", ""))
    if adapter_cls is None:
        raise AdapterNotImplemented(f"No adapter for source type {source.get('sourceType')!r}")
    return adapter_cls(source)


__all__ = [
    "AdapterNotImplemented",
    "CandidateWindow",
    "HealthResult",
    "SourceAdapter",
    "Mp4FileAdapter",
    "RtspAdapter",
    "OnvifAdapter",
    "WebRtcAdapter",
    "ADAPTERS_BY_TYPE",
    "get_adapter",
]
