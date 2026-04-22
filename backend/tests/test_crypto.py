"""Tests for AES-GCM token encryption."""
from __future__ import annotations

import base64
import secrets

import pytest
from cryptography.exceptions import InvalidTag

from syncup.ingest.crypto import decrypt_token, encrypt_token


def _make_key() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode()


@pytest.fixture(autouse=True)
def set_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNCUP_TOKEN_ENCRYPTION_KEY", _make_key())


def test_roundtrip() -> None:
    plaintext = "spotify-access-token-abc123"
    assert decrypt_token(encrypt_token(plaintext)) == plaintext


def test_long_token_roundtrip() -> None:
    plaintext = "x" * 4096
    assert decrypt_token(encrypt_token(plaintext)) == plaintext


def test_different_nonces_produce_different_ciphertexts() -> None:
    plaintext = "same-token"
    ct1 = encrypt_token(plaintext)
    ct2 = encrypt_token(plaintext)
    assert ct1 != ct2


def test_ciphertext_is_bytes() -> None:
    assert isinstance(encrypt_token("tok"), bytes)


def test_wrong_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    ct = encrypt_token("secret")
    monkeypatch.setenv("SYNCUP_TOKEN_ENCRYPTION_KEY", _make_key())
    with pytest.raises(InvalidTag):
        decrypt_token(ct)


def test_missing_env_var_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SYNCUP_TOKEN_ENCRYPTION_KEY")
    with pytest.raises(KeyError):
        encrypt_token("tok")


def test_bad_key_length_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNCUP_TOKEN_ENCRYPTION_KEY", base64.b64encode(b"tooshort").decode())
    with pytest.raises(ValueError, match="must be 16, 24, or 32 bytes"):
        encrypt_token("tok")


def test_truncated_ciphertext_raises() -> None:
    ct = encrypt_token("tok")
    with pytest.raises(ValueError):
        decrypt_token(ct[:4])
