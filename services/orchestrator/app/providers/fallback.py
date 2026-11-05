"""Try a primary model provider, then a local fallback when the primary is unavailable.

Only availability failures (rate limits, provider 5xx, timeouts, network
errors) move a request to the fallback. Invalid model output does not: that
is a quality signal to report, not to hide. The model that actually answered
is recorded per thread so the incident names it.
"""
from __future__ import annotations

import threading
from typing import Any

import httpx

from app.providers.base import ModelProvider


def is_availability_failure(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, (httpx.TimeoutException, httpx.TransportError))


class FallbackProvider(ModelProvider):
    def __init__(self, primary: ModelProvider, fallback: ModelProvider):
        self.primary, self.fallback = primary, fallback
        self._local = threading.local()

    @property
    def vision_model(self) -> str:
        return getattr(self._local, 'model', None) or getattr(self.primary, 'vision_model', '')

    def availability(self):
        primary = self.primary.availability() if hasattr(self.primary, 'availability') else {'ok': True}
        fallback = self.fallback.availability() if hasattr(self.fallback, 'availability') else {'ok': True}
        return {'ok': primary.get('ok') or fallback.get('ok'), 'model': primary.get('model'),
                'detail': f"{primary.get('detail', '')}; fallback {fallback.get('model', '')}: {fallback.get('detail', '')}"}

    def _call(self, method: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            result = getattr(self.primary, method)(*args, **kwargs)
            self._local.model = getattr(self.primary, 'vision_model', '')
            return result
        except Exception as exc:
            if not is_availability_failure(exc):
                raise
        result = getattr(self.fallback, method)(*args, **kwargs)
        self._local.model = f"{getattr(self.fallback, 'vision_model', '')} (fallback)"
        return result

    def review_event_evidence_base64(self, prompt, images, schema=None):
        return self._call('review_event_evidence_base64', prompt, images, schema)

    def review_event_evidence(self, prompt, image_paths, schema=None):
        return self._call('review_event_evidence', prompt, image_paths, schema)

    def summarize_incident(self, prompt, schema=None):
        return self._call('summarize_incident', prompt, schema)

    def suggest_actions(self, prompt, schema=None):
        return self._call('suggest_actions', prompt, schema)
