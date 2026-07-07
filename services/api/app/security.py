"""Password hashing helpers.

Uses stdlib PBKDF2-HMAC-SHA256 so local images need no compiled crypto
dependency. Swapping to argon2/bcrypt before real deployment is tracked in
docs/DEPLOYMENT_READINESS.md; the stored format is self-describing so a
future upgrade can re-hash on login.
"""

from __future__ import annotations

import hashlib
import hmac
import os

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 390_000


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS
    ).hex()
    return f"{_ALGORITHM}${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations_raw, salt, digest = stored.split("$", 3)
        iterations = int(iterations_raw)
    except ValueError:
        return False
    if algorithm != _ALGORITHM:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations
    ).hex()
    return hmac.compare_digest(candidate, digest)
