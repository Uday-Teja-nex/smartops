"""Try a primary model provider, then a local fallback when the primary is unavailable.

Only availability failures (rate limits, provider 5xx, timeouts, network
errors) move a request to the fallback. Invalid model output does not: that
is a quality signal to report, not to hide. The model that actually answered
is recorded per thread so the incident names it.

A circuit breaker stops a failing primary from costing every review its full
timeout: after `failure_threshold` consecutive availability failures the
primary is skipped for `cooldown_seconds`, then tried again with one request.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable

import httpx

from app.providers.base import ModelProvider


def is_availability_failure(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, (httpx.TimeoutException, httpx.TransportError))


class FallbackProvider(ModelProvider):
    def __init__(self, primary: ModelProvider, fallback: ModelProvider, *, failure_threshold: int = 2,
                 cooldown_seconds: float | None = None, clock: Callable[[], float] = time.monotonic):
        self.primary, self.fallback = primary, fallback
        self._local = threading.local()
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = (float(os.getenv('SMARTOPS_FALLBACK_COOLDOWN_SECONDS', '300'))
                                 if cooldown_seconds is None else cooldown_seconds)
        self._clock = clock
        self._lock = threading.Lock()
        self._failures = 0
        self._open_until = 0.0
        self._probing = False

    def _primary_allowed(self) -> bool:
        """Closed: always. Open: never until the cooldown ends. Then one probe."""
        with self._lock:
            if self._failures < self.failure_threshold:
                return True
            if self._clock() < self._open_until or self._probing:
                return False
            self._probing = True
            return True

    def _record(self, ok: bool) -> None:
        with self._lock:
            self._probing = False
            if ok:
                self._failures = 0
                return
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._open_until = self._clock() + self.cooldown_seconds

    def paused_seconds(self) -> float:
        with self._lock:
            if self._failures < self.failure_threshold:
                return 0.0
            return max(0.0, self._open_until - self._clock())

    @property
    def vision_model(self) -> str:
        return getattr(self._local, 'model', None) or getattr(self.primary, 'vision_model', '')

    def availability(self):
        primary = self.primary.availability() if hasattr(self.primary, 'availability') else {'ok': True}
        fallback = self.fallback.availability() if hasattr(self.fallback, 'availability') else {'ok': True}
        paused = self.paused_seconds()
        detail = primary.get('detail', '')
        if paused:
            detail = (f"{detail}; skipped for {paused:.0f} s after {self._failures} failed requests"
                      if detail else f"skipped for {paused:.0f} s after {self._failures} failed requests")
        return {'ok': primary.get('ok') or fallback.get('ok'), 'model': primary.get('model'),
                'detail': f"{detail}; fallback {fallback.get('model', '')}: {fallback.get('detail', '')}"}

    def _call(self, method: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if self._primary_allowed():
            try:
                result = getattr(self.primary, method)(*args, **kwargs)
            except Exception as exc:
                if not is_availability_failure(exc):
                    self._record(True)  # the provider answered; the output was the problem
                    raise
                self._record(False)
            else:
                self._record(True)
                self._local.model = getattr(self.primary, 'vision_model', '')
                return result
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
