"""ZADC — Zutfen Agentic Development Contract.

This package provides the canonical artifact substrate: common envelope
models, constrained identifiers/timestamps, deterministic canonical JSON,
SHA-256 sealing/verification, and a reproducible JSON Schema.

Public API:
    Types:
        ActorType       — Literal union of valid actor types.
        ArtifactType    — Literal union of valid artifact types.
        GlobalId        — URI-shaped global identifier (annotated str).
        SliceId         — Human-friendly slice identifier (annotated str).
        Sha256Digest    — Annotated str validated as sha256:<64hex>.
        GitSha          — Annotated str validated as 40 lowercase hex.

    Models:
        ArtifactEnvelope  — The common envelope shared by all artifacts.
        ProducerIdentity  — Identity of the producing actor.
        PolicyReference   — Reference to governing policy.
        Provenance        — Parent artifact IDs and content digest.

    Canonical JSON:
        canonical_json_bytes(value) -> bytes
        canonical_json_text(value)  -> str

    Digests:
        compute_content_digest(envelope) -> str
        seal_artifact(envelope)          -> ArtifactEnvelope
        verify_content_digest(envelope)  -> str

    Errors:
        DigestMissingError  — Envelope has not been sealed.
        DigestMismatchError — Stored digest does not match recomputed digest.
"""

from importlib.metadata import PackageNotFoundError, version

from zadc.canonical import CanonicalJSONTypeError, canonical_json_bytes, canonical_json_text
from zadc.digests import compute_content_digest, seal_artifact, verify_content_digest
from zadc.errors import DigestError, DigestMismatchError, DigestMissingError
from zadc.models.common import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
)
from zadc.types import (
    CONTRACT_VERSION,
    SCHEMA_ID,
    ActorType,
    ArtifactType,
    GitSha,
    GlobalId,
    Sha256Digest,
    SliceId,
)


def get_version() -> str:
    """Return the installed package version via importlib.metadata."""
    try:
        return version("zutfen-zadc")
    except PackageNotFoundError:  # pragma: no cover
        return "0.0.0+unknown"


__all__ = [
    # Version
    "get_version",
    # Constants
    "CONTRACT_VERSION",
    "SCHEMA_ID",
    # Types
    "ActorType",
    "ArtifactType",
    "GlobalId",
    "SliceId",
    "Sha256Digest",
    "GitSha",
    # Models
    "ArtifactEnvelope",
    "ProducerIdentity",
    "PolicyReference",
    "Provenance",
    # Canonical JSON
    "canonical_json_bytes",
    "canonical_json_text",
    "CanonicalJSONTypeError",
    # Digests
    "compute_content_digest",
    "seal_artifact",
    "verify_content_digest",
    # Errors
    "DigestError",
    "DigestMissingError",
    "DigestMismatchError",
]
