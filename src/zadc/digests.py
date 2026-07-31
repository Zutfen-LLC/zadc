"""Content digest computation, sealing, and verification for ZADC artifacts.

The content digest is SHA-256 of the ZADC Canonical JSON v0.1 bytes of
the artifact envelope, with the ``provenance.content_digest`` member
*removed entirely* from the canonical digest payload (not set to null).

FIX1-A correction: the ``content_digest`` key is completely removed from
the payload dict before canonical serialization, not set to ``None``.

FIX1-B correction: ``seal_artifact`` uses validated reconstruction
(``model_validate``) rather than unvalidated ``model_copy(update=...)``.

Public API:
- :func:`compute_content_digest`: Compute the digest for an envelope.
  Always removes any existing ``content_digest`` before computation.
- :func:`seal_artifact`: Return a new validated envelope with
  ``content_digest`` set to the computed digest.
- :func:`verify_content_digest`: Verify the stored digest matches.
"""

import hashlib
import hmac

from zadc.canonical import canonical_json_bytes
from zadc.errors import DigestMismatchError, DigestMissingError
from zadc.models.common import ArtifactEnvelope


def _envelope_to_digest_input(envelope: ArtifactEnvelope) -> bytes:
    """Convert an envelope to canonical JSON bytes with content_digest removed.

    The ``provenance.content_digest`` key is *removed entirely* from the
    payload dict before canonical serialization. The input model is never
    mutated. No other field is excluded.
    """
    data = envelope.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=False,
        exclude_defaults=False,
        exclude_unset=False,
    )

    # Remove content_digest entirely from the provenance sub-dict.
    provenance = data["provenance"]
    provenance.pop("content_digest", None)

    return canonical_json_bytes(data)


def get_digest_input_bytes(envelope: ArtifactEnvelope) -> bytes:
    """Return the exact canonical digest-input bytes for an envelope.

    This is a narrow, test-visible helper that exposes the digest payload
    so tests can assert the absence of ``content_digest`` from the raw bytes.
    It is not part of the public API surface used by consumers.
    """
    return _envelope_to_digest_input(envelope)


def compute_content_digest(envelope: ArtifactEnvelope) -> str:
    """Compute the content digest for an artifact envelope.

    The digest is ``sha256:`` followed by 64 lowercase hex characters.
    It is computed over canonical JSON bytes of the envelope with
    ``provenance.content_digest`` *removed entirely* from the payload.

    This function never mutates the input envelope. It is safe to call
    on both sealed and unsealed envelopes — the result is identical.

    Args:
        envelope: An :class:`ArtifactEnvelope` instance.

    Returns:
        The content digest string (e.g. ``"sha256:abcdef..."``).
    """
    canonical_bytes = _envelope_to_digest_input(envelope)
    digest_hex = hashlib.sha256(canonical_bytes).hexdigest()
    return f"sha256:{digest_hex}"


def seal_artifact(envelope: ArtifactEnvelope) -> ArtifactEnvelope:
    """Return a new validated envelope with the content digest set.

    Uses validated reconstruction: the full envelope payload is dumped,
    the digest is inserted, and the result is re-validated via
    ``model_validate``. This prevents unvalidated nested mutations.

    The input envelope is never mutated. Re-sealing an unmodified
    sealed envelope produces the same digest (idempotent).

    Args:
        envelope: An :class:`ArtifactEnvelope` instance.

    Returns:
        A new validated :class:`ArtifactEnvelope` with ``content_digest``
        populated.
    """
    digest = compute_content_digest(envelope)
    # Validated reconstruction: dump, insert digest, re-validate.
    data = envelope.model_dump(
        mode="python",
        by_alias=True,
        exclude_none=False,
        exclude_defaults=False,
        exclude_unset=False,
    )
    data["provenance"]["content_digest"] = digest
    return ArtifactEnvelope.model_validate(data)


def verify_content_digest(
    envelope: ArtifactEnvelope,
    *,
    repair: bool = False,
) -> str:
    """Verify that the stored content digest matches the recomputed digest.

    Uses constant-time comparison via ``hmac.compare_digest``. Never repairs.

    Args:
        envelope: An :class:`ArtifactEnvelope` instance.
        repair: Always ``False``. If ``True``, raises ``ValueError``.

    Returns:
        The expected (recomputed) content digest string.

    Raises:
        DigestMissingError: If ``content_digest`` is ``None``.
        DigestMismatchError: If stored != recomputed.
    """
    if repair:
        raise ValueError("repair is not supported; verification never repairs")

    stored = envelope.provenance.content_digest
    if stored is None:
        raise DigestMissingError("content_digest is absent; envelope has not been sealed")

    expected = compute_content_digest(envelope)

    if not hmac.compare_digest(stored, expected):
        raise DigestMismatchError(stored=stored, expected=expected)

    return expected


__all__ = [
    "compute_content_digest",
    "seal_artifact",
    "verify_content_digest",
    "get_digest_input_bytes",
]
