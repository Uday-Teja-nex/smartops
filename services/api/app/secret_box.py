"""Encrypt small secret blobs (notification credentials) at rest.

Fernet (AES-128-CBC + HMAC-SHA256) keyed by SMARTOPS_SECRETS_KEY. Production
refuses to start without an explicit key (see config). Development derives a
key from the JWT secret so local data stays readable across restarts.

Stored form: {"_enc": "<fernet token>"}. Rows written before encryption
(plain dicts) are still read, and are sealed on their next write.
"""
from __future__ import annotations

import base64
import hashlib
import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

ENVELOPE_KEY = "_enc"


@lru_cache
def _fernet() -> Fernet:
    settings = get_settings()
    if settings.secrets_key:
        return Fernet(settings.secrets_key.encode())
    derived = hashlib.sha256(b"smartops-dev-secret-box:" + settings.jwt_secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def seal(values: dict[str, Any]) -> dict[str, str]:
    token = _fernet().encrypt(json.dumps(values, separators=(",", ":")).encode())
    return {ENVELOPE_KEY: token.decode()}


def open_(stored: dict[str, Any] | None) -> dict[str, Any]:
    if not stored:
        return {}
    if ENVELOPE_KEY not in stored:
        return dict(stored)  # written before encryption at rest
    try:
        return json.loads(_fernet().decrypt(stored[ENVELOPE_KEY].encode()))
    except InvalidToken as exc:
        raise ValueError("Stored secret cannot be decrypted with the configured SMARTOPS_SECRETS_KEY") from exc


def is_sealed(stored: dict[str, Any] | None) -> bool:
    return bool(stored) and ENVELOPE_KEY in stored
