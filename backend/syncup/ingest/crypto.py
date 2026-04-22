"""AES-GCM encryption for OAuth tokens stored in the database."""
from __future__ import annotations

import base64
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12
_KEY_ENV = "SYNCUP_TOKEN_ENCRYPTION_KEY"
_VALID_KEY_LENGTHS = (16, 24, 32)


def _get_key() -> bytes:
    raw = base64.b64decode(os.environ[_KEY_ENV])
    if len(raw) not in _VALID_KEY_LENGTHS:
        raise ValueError(
            f"Token encryption key must be 16, 24, or 32 bytes (got {len(raw)}). "
            f"Set {_KEY_ENV} to a base64-encoded key of the correct length."
        )
    return raw


def encrypt_token(plaintext: str) -> bytes:
    nonce = secrets.token_bytes(_NONCE_BYTES)
    ct = AESGCM(_get_key()).encrypt(nonce, plaintext.encode(), None)
    return nonce + ct


def decrypt_token(ciphertext: bytes) -> str:
    if len(ciphertext) <= _NONCE_BYTES:
        raise ValueError(
            f"Ciphertext too short: expected >{_NONCE_BYTES} bytes, got {len(ciphertext)}"
        )
    nonce, ct = ciphertext[:_NONCE_BYTES], ciphertext[_NONCE_BYTES:]
    return AESGCM(_get_key()).decrypt(nonce, ct, None).decode()
