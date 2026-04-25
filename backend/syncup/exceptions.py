"""Shared application exceptions."""
from __future__ import annotations


class SyncUpError(Exception):
    """Application-level error with a machine-readable code.

    Raise this instead of HTTPException for domain errors — the global
    exception handler in app.py converts it to the standard error envelope.
    """

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
