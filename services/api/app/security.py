"""Password hashing helpers.

New hashes use argon2id (argon2-cffi defaults: RFC 9106 low-memory profile).
Hashes written by the earlier PBKDF2-HMAC-SHA256 scheme still verify, and
`needs_rehash` reports them so a successful login upgrades them in place.
"""

from __future__ import annotations

import hashlib
import hmac

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_LEGACY_ALGORITHM = "pbkdf2_sha256"
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _verify_legacy(password: str, stored: str) -> bool:
    try:
        algorithm, iterations_raw, salt, digest = stored.split("$", 3)
        iterations = int(iterations_raw)
        salt_bytes = bytes.fromhex(salt)
    except ValueError:
        return False
    if algorithm != _LEGACY_ALGORITHM:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations).hex()
    return hmac.compare_digest(candidate, digest)


def verify_password(password: str, stored: str) -> bool:
    if stored.startswith(f"{_LEGACY_ALGORITHM}$"):
        return _verify_legacy(password, stored)
    try:
        return _hasher.verify(stored, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored: str) -> bool:
    if stored.startswith(f"{_LEGACY_ALGORITHM}$"):
        return True
    try:
        return _hasher.check_needs_rehash(stored)
    except InvalidHashError:
        return True
