"""Narrow typed errors for ZADC digest verification.

These errors distinguish a *missing* digest (the envelope was never sealed)
from a *mismatched* digest (the envelope was modified after sealing). Neither
error type echoes the full artifact — only a short field path reference.
"""

from __future__ import annotations


class DigestError(Exception):
    """Base class for all digest-related errors.

    Public errors MUST NOT echo whole artifacts. Only a short
    human-readable message is carried.
    """


class DigestMissingError(DigestError):
    """Raised when a content digest is expected but absent.

    The envelope has not been sealed yet (``provenance.content_digest``
    is ``None``).
    """


class DigestMismatchError(DigestError):
    """Raised when the stored content digest does not match the recomputed digest.

    The envelope was modified after sealing, or the digest was corrupted.
    Only the stored and expected values are included — never the full artifact.
    """

    def __init__(self, stored: str, expected: str) -> None:
        self.stored = stored
        self.expected = expected
        super().__init__(f"content digest mismatch: stored={stored} expected={expected}")


__all__ = [
    "DigestError",
    "DigestMissingError",
    "DigestMismatchError",
]
