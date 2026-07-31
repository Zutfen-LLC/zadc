"""Constrained shared types for ZADC canonical artifacts.

This module defines:

- ``GlobalId``: URI-shaped identifiers following the ZADC GlobalId v0.1 profile.
  Canonical lowercase ASCII scheme, non-empty ASCII RFC 3986 scheme-specific
  part, valid uppercase ``%HH`` percent escapes, and canonical lowercase UUID URNs.
- ``SliceId``: Human-friendly bounded identifiers for slice and
  slice-instance references.
- ``TimestampField``: The ZADC Timestamp v0.1 annotated type with model-owned
  schema constraints for JSON Schema generation.

FIX3 changes:
- The GlobalId JSON Schema pattern is now percent-aware: ``%`` is accepted
  only as a complete uppercase ``%HH`` escape. The pattern rejects bare ``%``,
  incomplete escapes, non-hex escapes, and lowercase hex escapes.
- A UUID conditional (Draft 2020-12 ``if/then``) is emitted through the
  GlobalId custom type's ``__get_pydantic_json_schema__`` hook so every
  GlobalId field enforces canonical UUID URN form when the value starts with
  ``urn:uuid:``.
- The Timestamp v0.1 schema pattern now constrains hour (00-23), minute
  (00-59), second (00-59), and offset hour/minute to valid numeric ranges.
  A ``not`` constraint rejects ``-00:00``. ``format: date-time`` plus
  ``FormatChecker`` rejects invalid calendar dates.

All FIX3 business constraints are model-owned: they come from Pydantic type
metadata or custom ``__get_pydantic_json_schema__`` hooks, NOT from
exporter-side injection.

ZADC GlobalId v0.1 grammar (runtime + schema parity):

    scheme    = [a-z][a-z0-9+.-]*
    colon     = ":"
    ssp-char  = ASCII-URI-char | pct-escape
    pct       = "%" HEXUP HEXUP        ; uppercase hex only
    uuid-urn  = "urn:uuid:" uuid-text  ; canonical lowercase hyphenated UUID
    GlobalId  = scheme colon 1*ssp-char

ZADC Timestamp v0.1 grammar:

    date      = YYYY "-" MM "-" DD
    time      = HH(00-23) ":" MM(00-59) ":" SS(00-59) [ "." 1*6DIGIT ]
    offset    = "Z" | ( "+" / "-" ) HH(00-23) ":" MM(00-59)  ; not -00:00
    Timestamp = date "T" time offset

Uppercase T and Z required. Leap seconds (SS = 60) rejected in v0.1.
Unknown offset ``-00:00`` rejected.
"""

import re
import unicodedata
from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated, Any, Literal, cast

from pydantic import AfterValidator, StringConstraints
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

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
# Contract literal types (FIX2-A) — for const + required schema generation
# ---------------------------------------------------------------------------

#: The exact schema URI as a Literal so Pydantic emits a JSON Schema ``const``.
SchemaUriLiteral = Literal["https://schemas.zutfen.com/zadc/0.1/artifact.schema.json"]

#: The exact contract version as a Literal so Pydantic emits a JSON Schema ``const``.
ContractVersionLiteral = Literal["0.1.0"]

# ---------------------------------------------------------------------------
# Global identifier validation (FIX2-B + FIX3-A: ZADC GlobalId v0.1)
# ---------------------------------------------------------------------------

#: Canonical lowercase URI scheme: [a-z][a-z0-9+.-]*
_GLOBAL_ID_SCHEME_RE = re.compile(r"[a-z][a-z0-9+.\-]*")

#: RFC 3986 ASCII unreserved characters: A-Za-z0-9 -._~
_ASCII_UNRESERVED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")

#: RFC 3986 ASCII reserved characters (gen-delims + sub-delims).
_ASCII_RESERVED = set(":/?#[]@!$&'()*+,;=")

#: All ASCII characters allowed in the scheme-specific part of a GlobalId (excluding %).
_ASCII_URI_CHARS_NO_PCT = _ASCII_UNRESERVED | _ASCII_RESERVED

#: Canonical UUID URN pattern: urn:uuid: followed by canonical lowercase hyphenated UUID.
_CANONICAL_UUID_URN_RE = re.compile(
    r"urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


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


def _validate_percent_escapes(ssp: str) -> None:
    """Validate that all percent escapes are valid %HH with uppercase hex.

    Malformed escapes (``%``, ``%G``, ``%0g``) are rejected.
    Lowercase hex escapes (``%0a``) are rejected for canonical form.
    """
    i = 0
    n = len(ssp)
    while i < n:
        if ssp[i] == "%":
            if i + 2 >= n:
                raise ValueError(f"malformed percent-escape at position {i}: incomplete sequence")
            hex1 = ssp[i + 1]
            hex2 = ssp[i + 2]
            if hex1 not in "0123456789ABCDEF" or hex2 not in "0123456789ABCDEF":
                raise ValueError(
                    f"malformed percent-escape at position {i}: "
                    f"must be %HH with uppercase hex, got %{hex1}{hex2}"
                )
            i += 3
        else:
            i += 1


def validate_global_id(value: str) -> str:
    """Validate a URI-shaped global identifier (ZADC GlobalId v0.1).

    A global ID MUST:
    - be a non-empty string;
    - have a canonical lowercase URI scheme matching [a-z][a-z0-9+.-]*;
    - contain at least one ASCII RFC 3986 URI character after the colon;
    - contain only ASCII RFC 3986 unreserved/reserved characters or valid
      uppercase ``%HH`` percent escapes — raw whitespace, controls, Unicode,
      backslashes, quotes, angle brackets, and other forbidden characters
      are rejected rather than normalized;
    - if the scheme is ``urn:uuid:``, match the canonical lowercase form
      ``urn:uuid:`` followed by a valid hyphenated UUID.

    This validator does NOT make network calls or attempt scheme-specific
    resource resolution.
    """
    if not isinstance(value, str):
        raise TypeError("global identifier must be a string")
    if not value:
        raise ValueError("global identifier must not be empty")

    # Reject any non-ASCII character — GlobalId v0.1 is ASCII-only.
    for idx, ch in enumerate(value):
        if ord(ch) > 127:
            raise ValueError(
                f"global identifier contains non-ASCII character at position {idx}: U+{ord(ch):04X}"
            )

    # Also reject Unicode category C characters (control/format chars are ASCII < 128).
    _reject_unicode_category_c(value)

    # Find the first colon — this separates the scheme from the scheme-specific part.
    colon_pos = value.find(":")
    if colon_pos <= 0:
        raise ValueError(f"global identifier must have a valid URI scheme: {value!r}")

    scheme = value[:colon_pos]
    ssp = value[colon_pos + 1 :]

    # Validate canonical lowercase scheme.
    if not _GLOBAL_ID_SCHEME_RE.fullmatch(scheme):
        raise ValueError(
            f"global identifier scheme must be canonical lowercase [a-z][a-z0-9+.-]*: {scheme!r}"
        )

    # Scheme-specific part must be non-empty.
    if not ssp:
        raise ValueError(
            f"global identifier must have at least one character after the scheme colon: {value!r}"
        )

    # Validate percent escapes (must be valid %HH uppercase).
    _validate_percent_escapes(ssp)

    # Every character in the SSP must be an allowed ASCII URI character (or part of a % escape).
    for idx, ch in enumerate(ssp):
        if ch == "%":
            continue  # already validated as part of percent escape
        if ch not in _ASCII_URI_CHARS_NO_PCT:
            raise ValueError(
                f"global identifier contains forbidden character {ch!r} "
                f"at position {colon_pos + 1 + idx} in scheme-specific part"
            )

    # UUID URN canonical validation — detect case-insensitively, require canonical lowercase.
    if (
        scheme == "urn"
        and ssp[:5].lower() == "uuid:"
        and not _CANONICAL_UUID_URN_RE.fullmatch(value)
    ):
        raise ValueError(f"urn:uuid identifiers must be canonical lowercase: {value!r}")

    return value


# ---------------------------------------------------------------------------
# GlobalId JSON Schema patterns (FIX3-A: model-owned, percent-aware)
# ---------------------------------------------------------------------------

#: Portable percent-aware GlobalId base pattern for JSON Schema.
#: Each character in the SSP is EITHER an ordinary RFC 3986 URI character
#: (no bare %) OR a complete uppercase %HH escape.
#:
#: This rejects: bare %, incomplete escapes (%2, %), non-hex (%GG), and
#: lowercase hex (%2f, %0a).
_GLOBAL_ID_BASE_PATTERN = (
    r"^[a-z][a-z0-9+.\-]*:"
    r"(?:[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=]|%[0-9A-F]{2})+$"
)

#: Exact canonical UUID URN pattern.
_UUID_URN_PATTERN = r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


class _GlobalIdJsonSchemaModifier:
    """Custom schema hook for GlobalId to inject the allOf/if/then constraint.

    This is model-owned metadata, not exporter-side mutation. When used as an
    Annotated metadata element, Pydantic calls ``__get_pydantic_json_schema__``
    during ``model_json_schema()`` generation, so the constraint is present in
    the raw model schema before any exporter post-processing.
    """

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: Any) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        # Build the model-owned GlobalId schema: base pattern + UUID conditional.
        result: dict[str, Any] = {"type": "string", "minLength": json_schema.get("minLength", 1)}
        result["allOf"] = [
            {
                "pattern": _GLOBAL_ID_BASE_PATTERN,
            },
            {
                "if": {"pattern": "^urn:[uU][uU][iI][dD]:"},
                "then": {"pattern": _UUID_URN_PATTERN},
            },
        ]
        return result


#: GlobalId type with model-owned schema constraints.
#: StringConstraints provides the base pattern for runtime validation.
#: _GlobalIdJsonSchemaModifier provides the allOf/if/then JSON Schema via
#: __get_pydantic_json_schema__.
GlobalId = Annotated[
    str,
    StringConstraints(min_length=1, pattern=_GLOBAL_ID_BASE_PATTERN),
    _GlobalIdJsonSchemaModifier,
    AfterValidator(validate_global_id),
]


#: GlobalIdUuidUrn — retained for backward compat but now equivalent to GlobalId.
GlobalIdUuidUrn = GlobalId


# ---------------------------------------------------------------------------
# Slice identifier validation (FIX1-D)
# ---------------------------------------------------------------------------

#: Allowed characters for slice IDs: uppercase letters, digits, and hyphens.
_SLICE_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]*[A-Z0-9]$|^[A-Z0-9]$")

_SLICE_ID_PATTERN = r"^[A-Z0-9]([A-Z0-9\-]*[A-Z0-9])?$"


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


SliceId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=_SLICE_ID_PATTERN),
    AfterValidator(validate_slice_id),
]


# ---------------------------------------------------------------------------
# ZADC Timestamp v0.1 grammar (FIX2-C + FIX3-B: model-owned schema)
# ---------------------------------------------------------------------------

#: The exact ZADC Timestamp v0.1 regex pattern with numeric ranges.
#:
#: Constrains:
#: - All digits are ASCII [0-9] (not Unicode \d which accepts Arabic-Indic etc.)
#: - Year: not 0000 (rejected by pinned RFC 3339 format validator)
#: - Hour: 00-23 (rejects 24+)
#: - Minute: 00-59 (rejects 60+)
#: - Second: 00-59 (rejects 60+, i.e. leap seconds)
#: - Offset hour: 00-23
#: - Offset minute: 00-59
#: - Fractional seconds: 1-6 digits
#:
#: Does NOT independently reject:
#: - -00:00 (handled by the not constraint below)
#: - Invalid calendar dates (handled by format: date-time + FormatChecker)
TIMESTAMP_V0_1_PATTERN = (
    r"^(?!0000)[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
    r"(?:\.[0-9]{1,6})?"
    r"(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])$"
)

#: Compiled timestamp regex for runtime fullmatch.
_TIMESTAMP_RE = re.compile(TIMESTAMP_V0_1_PATTERN)

#: Pattern matching -00:00 (for the model-owned not constraint).
_TIMESTAMP_NEG_00_00_PATTERN = r"^.*-00:00$"


def validate_timestamp(value: str) -> str:
    """Validate a timestamp string against the ZADC Timestamp v0.1 grammar.

    Accepts only ``YYYY-MM-DDTHH:MM:SS[.fraction](Z|±HH:MM)`` with uppercase
    T and Z. Rejects spaces, arbitrary separators, basic date/time forms,
    week dates, ordinal dates, offsets without a colon, timezone-free strings,
    lowercase t/z, >6 fractional digits, leap seconds (:60), unknown offset
    (-00:00), invalid dates, invalid times, invalid offsets, and trailing data.

    Does NOT normalize — returns the validated string as-is. The model's
    field_validator normalizes to UTC after this check passes.

    Args:
        value: A timestamp string to validate.

    Returns:
        The validated timestamp string (unchanged).

    Raises:
        ValueError: If the timestamp does not match the ZADC Timestamp v0.1
            grammar or fails calendar/wall-clock/offset validation.
    """
    if not isinstance(value, str):
        raise TypeError(f"timestamp must be a string, not {type(value).__name__}")
    if not value:
        raise ValueError("timestamp must not be empty")

    # Step 1: Exact regex fullmatch (handles component ranges).
    if not _TIMESTAMP_RE.fullmatch(value):
        raise ValueError(f"timestamp does not match ZADC Timestamp v0.1 grammar: {value!r}")

    # Step 2: Validate calendar date (FormatChecker-compatible logic).
    date_part = value[:10]  # YYYY-MM-DD

    year = int(date_part[:4])
    month = int(date_part[5:7])
    day = int(date_part[8:10])
    _validate_calendar_date(year, month, day)

    # Step 3: Reject -00:00 explicitly (the regex pattern already handles this
    # via the offset alternatives, but double-check for safety).
    offset_part = value[19:]
    if "." in offset_part:
        # Fractional seconds present — offset starts after the fraction.
        frac_start = 19  # position after HH:MM:SS
        j = frac_start + 1  # skip the '.'
        while j < len(value) and value[j].isdigit():
            j += 1
        offset_part = value[j:]

    if offset_part == "-00:00":
        raise ValueError(
            "timestamp offset -00:00 is rejected in v0.1 (unknown offset collapsed into UTC)"
        )

    return value


def _validate_calendar_date(year: int, month: int, day: int) -> None:
    """Validate that the given year/month/day is a real calendar date."""
    if month < 1 or month > 12:
        raise ValueError(f"timestamp has invalid month: {month}")
    if day < 1:
        raise ValueError(f"timestamp has invalid day: {day}")
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    # Leap year check.
    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    if is_leap:
        days_in_month[1] = 29

    if day > days_in_month[month - 1]:
        raise ValueError(f"timestamp has invalid day {day} for month {month} (year {year})")


def normalize_timestamp_to_utc(value: str) -> datetime:
    """Parse a ZADC Timestamp v0.1 string and normalize to UTC datetime.

    The input MUST already pass ``validate_timestamp``. This function parses
    the validated string deterministically without relying on
    ``datetime.fromisoformat`` (which accepts broader syntax).

    Args:
        value: A timestamp string that passed ``validate_timestamp``.

    Returns:
        A timezone-aware ``datetime`` normalized to UTC.
    """
    # We know the format is exact from validate_timestamp.
    date_part = value[:10]
    time_part = value[11:19]

    year = int(date_part[:4])
    month = int(date_part[5:7])
    day = int(date_part[8:10])
    hours = int(time_part[:2])
    minutes = int(time_part[3:5])
    seconds = int(time_part[6:8])

    # Extract fractional microseconds.
    microseconds = 0
    offset_part = value[19:]
    frac_str = ""
    if "." in offset_part:
        dot_pos = value.index(".", 19)
        # Read digits after the dot.
        end_pos = dot_pos + 1
        while end_pos < len(value) and value[end_pos].isdigit():
            end_pos += 1
        frac_str = value[dot_pos + 1 : end_pos]
        offset_part = value[end_pos:]

    if frac_str:
        # Pad to 6 digits for microseconds.
        microseconds = int(frac_str.ljust(6, "0")[:6])

    # Parse offset.
    if offset_part == "Z" or offset_part == "+00:00":
        tz_offset = UTC
    else:
        sign = -1 if offset_part[0] == "-" else 1
        off_hours = int(offset_part[1:3])
        off_minutes = int(offset_part[4:6])
        tz_offset = timezone(timedelta(hours=off_hours, minutes=off_minutes) * sign)

    dt = datetime(year, month, day, hours, minutes, seconds, microseconds, tz_offset)
    return dt.astimezone(UTC)


# ---------------------------------------------------------------------------
# Timestamp JSON Schema modifier (FIX3-B/FIX3-C: model-owned)
# ---------------------------------------------------------------------------


class _TimestampJsonSchemaModifier:
    """Custom schema hook for timestamp fields to inject model-owned constraints.

    Emits the ZADC Timestamp v0.1 pattern (with numeric ranges), a ``not``
    constraint rejecting -00:00, and ``format: date-time`` for FormatChecker
    calendar validation. All constraints are model-owned and appear in the
    raw model_json_schema() output before exporter post-processing.
    """

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: Any) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        # Add the exact timestamp pattern.
        json_schema["pattern"] = TIMESTAMP_V0_1_PATTERN
        # Add not constraint for -00:00.
        json_schema["not"] = {"pattern": _TIMESTAMP_NEG_00_00_PATTERN}
        return cast(JsonSchemaValue, json_schema)


#: The timestamp annotation type with model-owned schema constraints.
#: Used as an Annotated[] metadata element on datetime fields.
TimestampField = _TimestampJsonSchemaModifier


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
    "TIMESTAMP_V0_1_PATTERN",
    "ActorType",
    "ArtifactType",
    "ContractVersionLiteral",
    "GlobalId",
    "GlobalIdUuidUrn",
    "SliceId",
    "Sha256Digest",
    "GitSha",
    "SchemaUriLiteral",
    "TimestampField",
    "validate_global_id",
    "validate_slice_id",
    "validate_sha256_digest",
    "validate_git_sha",
    "validate_timestamp",
    "normalize_timestamp_to_utc",
]
