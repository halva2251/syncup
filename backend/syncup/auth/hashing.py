"""Password hashing with argon2id."""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# argon2id defaults (time=3, memory=65536, parallelism=4) are OWASP-recommended.
_ph = PasswordHasher()

# Pre-computed dummy hash for constant-time failure on unknown emails.
_DUMMY_HASH = _ph.hash("syncup-dummy-timing-sentinel")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    """Return True if password matches the stored hash, False otherwise."""
    try:
        return _ph.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verify_password_dummy(password: str) -> None:
    """Run a hash verification against a dummy hash.

    Call this on the "user not found" path so the response time is
    indistinguishable from the "wrong password" path.
    """
    verify_password(_DUMMY_HASH, password)


def needs_rehash(stored_hash: str) -> bool:
    """Return True if the hash was produced with outdated parameters."""
    return _ph.check_needs_rehash(stored_hash)
