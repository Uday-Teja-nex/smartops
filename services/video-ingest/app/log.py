"""Structured JSON logging for the video-ingest service.

Each service carries its own copy of this tiny helper because Compose builds
use per-service contexts (services/<name>/) and cannot reach ../shared.
Keep the copies in sync when changing the format.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Any

SERVICE_NAME = "video-ingest"


def log(event: str, level: str = "info", **fields: Any) -> None:
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "service": SERVICE_NAME,
        "level": level,
        "event": event,
        **fields,
    }
    print(json.dumps(record, default=str), file=sys.stdout, flush=True)
