"""Credentials are encrypted at rest and legacy plaintext rows still read."""
import pytest

from app import secret_box


def test_seal_and_open_round_trip_without_plaintext():
    stored = secret_box.seal({"botToken": "999:abc", "chatId": "42"})
    assert list(stored) == ["_enc"] and "999:abc" not in stored["_enc"]
    assert secret_box.open_(stored) == {"botToken": "999:abc", "chatId": "42"}
    assert secret_box.is_sealed(stored)


def test_legacy_plaintext_rows_still_read():
    assert secret_box.open_({"url": "https://hooks.example.test"}) == {"url": "https://hooks.example.test"}
    assert secret_box.open_(None) == {}


def test_wrong_key_fails_loudly(monkeypatch):
    stored = secret_box.seal({"secret": "s"})
    from cryptography.fernet import Fernet
    monkeypatch.setattr(secret_box, "_fernet", lambda: Fernet(Fernet.generate_key()))
    with pytest.raises(ValueError, match="SMARTOPS_SECRETS_KEY"):
        secret_box.open_(stored)
