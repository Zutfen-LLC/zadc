"""Content digest computation, sealing, and verification for ZADC artifacts.

The content digest is SHA-256 of the ZADC Canonical JSON v0.1 bytes of
the artifact envelope, with the ``provenance.content_digest`` field
excluded (set to ``None``) before serialization.

Public API:
- :func:`compute_content_digest`: Compute the digest for an unsealed or
  sealed envelope. Always ignores any existing ``content_digest``.
- :func:`seal_artifact`: Return a new immutable copy of the envelope with
  ``content_digest`` set to the computed digest.
- :func:`verify_content_digest`: Verify that the stored digest matches the
  recomputed digest. Raises :class:`DigestMissingError` if no digest is
  present, or :class:`DigestMismatchError` if the digests differ.
"""

from __future__ import annotations

import hashlib
import hmac

from zadc.canonical import canonical_json_bytes
from zadc.errors import DigestMismatchError, DigestMissingError
from zadc.models.common import ArtifactEnvelope


def _envelope_to_digest_input(envelope: ArtifactEnvelope) -> bytes:
    """Convert an envelope to canonical JSON bytes with content_digest excluded.

    The ``provenance.content_digest`` field is set to ``None`` before
    serialization. The input model is never mutated.
    """
    # Dump the model to a JSON-compatible dict (with aliases, all fields).
    data = envelope.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=False,
    )

    # Remove the content_digest from the provenance sub-dict.
    # This is the ONLY field excluded from digest computation.
    provenance = data["provenance"]
    provenance["content_digest"] = None

    return canonical_json_bytes(data)


def compute_content_digest(envelope: ArtifactEnvelope) -> str:
    """Compute the content digest for an artifact envelope.

    The digest is ``sha256:`` followed by 64 lowercase hex characters.
    It is computed over the canonical JSON bytes of the envelope with
    ``provenance.content_digest`` set to ``None``.

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
    """Return a new immutable copy of the envelope with the content digest set.

    The input envelope is never mutated. If the envelope is already sealed
    (``content_digest`` is not ``None``), the existing digest is replaced
    with a freshly computed one. However, since the digest is computed
    over the envelope with ``content_digest`` set to ``None``, re-sealing
    an unmodified envelope produces the same digest (idempotent).

    The returned model is a new frozen instance.

    Args:
        envelope: An :class:`ArtifactEnvelope` instance.

    Returns:
        A new :class:`ArtifactEnvelope` with ``content_digest`` populated.
    """
    digest = compute_content_digest(envelope)
    # Use model_copy with update to create a new frozen instance.
    new_provenance = envelope.provenance.model_copy(update={"content_digest": digest})
    return envelope.model_copy(update={"provenance": new_provenance})


def verify_content_digest(
    envelope: ArtifactEnvelope,
    *,
    repair: bool = False,
) -> str:
    """Verify that the stored content digest matches the recomputed digest.

    The recomputed digest is computed the same way as
    :func:`compute_content_digest` — over canonical bytes with
    ``content_digest`` set to ``None``.

    Args:
        envelope: An :class:`ArtifactEnvelope` instance.
        repair: If ``True``, the function repairs a mismatched digest.
            Defaults to ``False`` — the function never repairs.

    Returns:
        The expected (recomputed) content digest string.

    Raises:
        DigestMissingError: If ``content_digest`` is ``None`` (envelope
            has not been sealed).
        DigestMismatchError: If the stored digest does not match the
            recomputed digest. Never raised when ``repair=True``.

    .. note::
        The ``repair`` parameter is intentionally not exposed in the public
        API documentation. Verification should never repair. The parameter
        exists only for internal consistency testing and is always ``False``
        when called from public code paths.
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
]
