"""Constrained shared types for ZADC canonical artifacts.

This module defines two distinct identifier classes:

- ``GlobalId``: URI-shaped identifiers for artifact, project, actor, run,
  and policy references. Must have a syntactically valid URI scheme
  (e.g. ``urn:uuid:``, ``zutfen:``, ``github:``).
- ``SliceId``: Human-friendly bounded identifiers for slice and
  slice-instance references. Rejects Unicode category C characters
  (controls, surrogates, format), whitespace injection, and blank values.

All public types enforce strict input validation at construction.
"""

import re
import unicodedata
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import AfterValidator, StringConstraints

# ---------------------------------------------------------------------------
# Contract-level constants (architecture section 10)
# ---------------------------------------------------------------------------

CONTRACT_VERSION: str = "0.1.0"

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
# Global identifier validation (FIX1-D)
# ---------------------------------------------------------------------------

#: Pattern for a valid URI scheme component per RFC 3986.
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*$")


def _reject_unicode_category_c(value: str) -> None:
    """Reject all Unicode category C characters (controls, surrogates, format).

    This covers Cc (control), Cf (format), Cs (surrogate), Co (private use),
    and Cn (unassigned). These are collectively unsafe in identifiers.
    """
    for ch in value:
        cat = unicodedata.category(ch)
        if cat.startswith("C"):
            raise ValueError(
                f"identifier contains Unicode category {cat} character: U+{ord(ch):04X}"
            )


def validate_global_id(value: str) -> str:
    """Validate a URI-shaped global identifier.

    A global ID MUST:
    - be a non-empty string;
    - contain no Unicode category C characters;
    - have a syntactically valid URI scheme (e.g. ``urn:uuid:``, ``zutfen:``,
      ``github:``);
    - if the scheme is ``urn:uuid:``, parse as a valid UUID URN in canonical
      lowercase form.

    This validator does NOT make network calls.
    """
    if not isinstance(value, str):
        raise TypeError("global identifier must be a string")
    if not value:
        raise ValueError("global identifier must not be empty")
    if value.strip() != value:
        raise ValueError("global identifier must not have leading/trailing whitespace")
    _reject_unicode_category_c(value)

    parsed = urlparse(value)
    scheme = parsed.scheme
    if not scheme or not _SCHEME_RE.match(scheme):
        raise ValueError(f"global identifier must have a valid URI scheme: {value!r}")

    # For urn:uuid: identifiers, validate canonical lowercase form.
    if scheme == "urn" and value.lower().startswith("urn:uuid:"):
        uuid_part = value[len("urn:uuid:") :]
        uuid_lower = uuid_part.lower()
        if uuid_lower != uuid_part:
            raise ValueError(f"urn:uuid identifiers must use lowercase hex: {value!r}")
        # Validate it parses as a real UUID.
        from uuid import UUID

        try:
            UUID(uuid_part)
        except ValueError as exc:
            raise ValueError(f"invalid urn:uuid value: {value!r}") from exc

    return value


#: URI pattern: scheme followed by colon. Scheme must start with a letter.
#: Unicode control character rejection is enforced by the AfterValidator.
_URI_PATTERN = r"^[a-zA-Z][a-zA-Z0-9+.\-]*:"

GlobalId = Annotated[
    str,
    StringConstraints(min_length=1, pattern=_URI_PATTERN),
    AfterValidator(validate_global_id),
]


# ---------------------------------------------------------------------------
# Slice identifier validation (FIX1-D)
# ---------------------------------------------------------------------------

#: Allowed characters for slice IDs: uppercase letters, digits, and hyphens.
_SLICE_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]*[A-Z0-9]$|^[A-Z0-9]$")


def validate_slice_id(value: str) -> str:
    """Validate a human-friendly slice identifier.

    A slice ID MUST:
    - be a non-empty string;
    - contain only uppercase letters, digits, and hyphens;
    - start and end with a letter or digit;
    - contain no Unicode category C characters;
    - contain no whitespace, path separators, or injection characters.

    Examples of valid slice IDs: ``ZADC-001A1``, ``ENG-PORTAL-RECEIPTS-001A-FIX1``.
    """
    if not isinstance(value, str):
        raise TypeError("slice identifier must be a string")
    if not value:
        raise ValueError("slice identifier must not be empty")
    if value.strip() != value:
        raise ValueError("slice identifier must not have leading/trailing whitespace")
    _reject_unicode_category_c(value)
    if not _SLICE_ID_RE.match(value):
        raise ValueError(
            f"slice identifier must match [A-Z0-9-]+ grammar (uppercase, "
            f"digits, hyphens; start/end alphanumeric): {value!r}"
        )
    return value


#: Allowed characters for slice IDs: uppercase letters, digits, and hyphens.
_SLICE_ID_PATTERN = r"^[A-Z0-9]([A-Z0-9\-]*[A-Z0-9])?$"

SliceId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=_SLICE_ID_PATTERN),
    AfterValidator(validate_slice_id),
]


# ---------------------------------------------------------------------------
# Digest and SHA validation
# ---------------------------------------------------------------------------

_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def validate_sha256_digest(value: str) -> str:
    """Validate a SHA-256 digest string."""
    if not isinstance(value, str):
        raise TypeError("sha256 digest must be a string")
    if not _SHA256_PATTERN.match(value):
        raise ValueError("sha256 digest must be 'sha256:' followed by 64 lowercase hex characters")
    return value


def validate_git_sha(value: str) -> str:
    """Validate a Git SHA string."""
    if not isinstance(value, str):
        raise TypeError("git sha must be a string")
    if not _GIT_SHA_PATTERN.match(value):
        raise ValueError("git sha must be exactly 40 lowercase hex characters")
    return value


Sha256Digest = Annotated[
    str,
    StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$"),
    AfterValidator(validate_sha256_digest),
]

GitSha = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9a-f]{40}$"),
    AfterValidator(validate_git_sha),
]


__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_ID",
    "ActorType",
    "ArtifactType",
    "GlobalId",
    "SliceId",
    "Sha256Digest",
    "GitSha",
    "validate_global_id",
    "validate_slice_id",
    "validate_sha256_digest",
    "validate_git_sha",
]
