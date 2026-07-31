"""Constrained shared types for ZADC canonical artifacts.

All public types in this module are strict, immutable, and extra=forbid
where applicable. They enforce the identifier and digest constraints
defined in ZADC architecture sections 9 and 10.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator

# ---------------------------------------------------------------------------
# Contract-level constants (architecture section 10)
# ---------------------------------------------------------------------------

#: The ZADC contract version for this implementation.
CONTRACT_VERSION: str = "0.1.0"

#: The canonical schema identifier embedded in every artifact envelope.
SCHEMA_ID: str = "https://schemas.zutfen.com/zadc/0.1/artifact.schema.json"

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

#: Valid actor types (architecture section 6, section 10 producer.actor_type).
ActorType = Literal[
    "human",
    "agent",
    "ci",
    "validator",
    "service",
]

#: Valid artifact types (architecture section 11, expanded for this foundation).
ArtifactType = Literal[
    "packet",
    "completion_report",
    "certification_manifest",
    "review_report",
    "decision_record",
    "workflow_bundle",
    "evidence_artifact",
    "observation",
]

# ---------------------------------------------------------------------------
# Identifier validation
# ---------------------------------------------------------------------------

# Reject ASCII control characters (C0 and DEL) in identifiers.
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def validate_stable_id(value: str) -> str:
    """Validate a stable identifier string.

    A stable ID MUST:
    - be non-empty after stripping surrounding whitespace;
    - contain no ASCII control characters;
    - be URI-shaped (supporting urn:uuid, zutfen:, github:, and similar
      scheme-prefixed identifiers or bare slug identifiers).

    The validation does NOT enforce a specific scheme so that the type
    remains forward-compatible with future identifier schemes.
    """
    if not isinstance(value, str):
        raise TypeError("stable identifier must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError("stable identifier must not be empty or whitespace-only")
    if stripped != value:
        raise ValueError("stable identifier must not have leading/trailing whitespace")
    if _CONTROL_RE.search(value):
        raise ValueError("stable identifier must not contain control characters")
    return value


#: Pydantic AfterValidator alias for stable IDs.
StableIdValidator = AfterValidator(validate_stable_id)

#: Annotated string type for stable identifiers usable in Pydantic models.
StableId = Annotated[str, StableIdValidator]

# ---------------------------------------------------------------------------
# Digest and SHA validation
# ---------------------------------------------------------------------------

#: Pattern for a SHA-256 digest with lowercase hex.
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

#: Pattern for a 40-character lowercase hex Git SHA.
_GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def validate_sha256_digest(value: str) -> str:
    """Validate a SHA-256 digest string.

    Must be exactly ``sha256:`` followed by 64 lowercase hex characters.
    """
    if not isinstance(value, str):
        raise TypeError("sha256 digest must be a string")
    if not _SHA256_PATTERN.match(value):
        raise ValueError("sha256 digest must be 'sha256:' followed by 64 lowercase hex characters")
    return value


def validate_git_sha(value: str) -> str:
    """Validate a Git SHA string.

    Must be exactly 40 lowercase hex characters.
    """
    if not isinstance(value, str):
        raise TypeError("git sha must be a string")
    if not _GIT_SHA_PATTERN.match(value):
        raise ValueError("git sha must be exactly 40 lowercase hex characters")
    return value


#: Annotated string type for SHA-256 digests.
Sha256Digest = Annotated[str, AfterValidator(validate_sha256_digest)]

#: Annotated string type for Git SHAs.
GitSha = Annotated[str, AfterValidator(validate_git_sha)]


__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_ID",
    "ActorType",
    "ArtifactType",
    "Sha256Digest",
    "GitSha",
    "StableId",
    "StableIdValidator",
    "validate_sha256_digest",
    "validate_git_sha",
    "validate_stable_id",
]
