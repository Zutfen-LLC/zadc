"""ZADC Canonical JSON v0.1.

This module defines and implements the deterministic canonical JSON
serialization profile used for content digest computation.

Profile rules (ZADC Canonical JSON v0.1):

1. **Encoding**: UTF-8 bytes, no BOM, no trailing newline.
2. **Object keys**: Recursively sorted by Unicode code-point order (ascending).
3. **Separators**: Compact — `","` and `":"` with no whitespace.
4. **Unicode**: Direct UTF-8 output with valid JSON escaping (``ensure_ascii=False``).
5. **Data types**: After model conversion, only ``None`` (→ ``null``),
   ``bool``, ``str``, ``int``, ``list``, and string-keyed ``dict`` are
   permitted.
6. **Rejected types**: ``float`` (including ``-0.0``, ``NaN``, ``Infinity``),
   ``Decimal``, ``bytes``, ``set``, ``frozenset``, non-string keys,
   and arbitrary objects.
7. **Datetime normalization**: All timezone-aware datetimes are normalized
   to UTC and serialized as RFC 3339 strings with uppercase ``Z``.
8. **Determinism**: Output is idempotent and independent of insertion order
   and ``PYTHONHASHSEED``.

The no-float rule is intentional cross-language digest hardening for v0.1.
Floating-point representations vary across languages, platforms, and
library versions, making them unsuitable for deterministic digest
computation. Integer quantities and string-encoded values should be used
instead. This rule may be revisited in a future contract version if a
deterministic float encoding profile is adopted.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any, Never
from uuid import UUID

# ---------------------------------------------------------------------------
# Type checking for canonical JSON compatibility
# ---------------------------------------------------------------------------


class CanonicalJSONTypeError(TypeError):
    """Raised when a value contains a type not permitted in canonical JSON."""


def _check_float(value: float) -> Never:
    """Reject all floats including -0.0, NaN, and Infinity."""
    raise CanonicalJSONTypeError(
        f"floats are not permitted in canonical JSON v0.1 (got {value!r}); "
        "use int or string-encoded values instead"
    )


def _normalize_value(value: Any) -> Any:
    """Recursively normalize a Python value for canonical JSON serialization.

    Performs type checking and datetime normalization. Returns a new
    structure composed only of ``None``, ``bool``, ``str``, ``int``,
    ``list``, and string-keyed ``dict``.

    Raises:
        CanonicalJSONTypeError: If a float, Decimal, bytes, set, frozenset,
            tuple, non-string key, or arbitrary object is encountered.
    """
    # Fast path for the most common JSON-native types.
    if value is None:
        return None
    if value is True or value is False:  # Must check before int (bool is subclass)
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        _check_float(value)

    from decimal import Decimal

    if isinstance(value, Decimal):
        raise CanonicalJSONTypeError(
            "Decimal is not permitted in canonical JSON v0.1; "
            "use int or string-encoded values instead"
        )

    if isinstance(value, bytes):
        raise CanonicalJSONTypeError(
            "bytes are not permitted in canonical JSON v0.1; use str with an explicit encoding"
        )

    if isinstance(value, bytearray):
        raise CanonicalJSONTypeError(
            "bytearray is not permitted in canonical JSON v0.1; use str with an explicit encoding"
        )

    if isinstance(value, (set, frozenset)):
        raise CanonicalJSONTypeError(
            "sets are not permitted in canonical JSON v0.1; use a list with explicit ordering"
        )

    if isinstance(value, datetime):
        return _normalize_datetime(value)

    if isinstance(value, date):
        # date (not datetime) — reject to avoid ambiguity
        raise CanonicalJSONTypeError(
            "bare date objects are not permitted in canonical JSON v0.1; "
            "pass a timezone-aware datetime instead"
        )

    if isinstance(value, UUID):
        raise CanonicalJSONTypeError(
            "UUID objects are not permitted in canonical JSON v0.1; "
            "convert to a 'urn:uuid:...' string before serialization"
        )

    if isinstance(value, list):
        return [_normalize_value(item) for item in value]

    if isinstance(value, tuple):
        raise CanonicalJSONTypeError(
            "tuples are not permitted in canonical JSON v0.1; use a list instead"
        )

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, val in value.items():
            if not isinstance(key, str):
                raise CanonicalJSONTypeError(
                    f"non-string dict key not permitted in canonical JSON v0.1 "
                    f"(got {type(key).__name__}: {key!r})"
                )
            result[key] = _normalize_value(val)
        return result

    # Reject any other type — this catches arbitrary objects.
    raise CanonicalJSONTypeError(
        f"objects of type {type(value).__name__} are not permitted in canonical JSON v0.1"
    )


def _normalize_datetime(value: datetime) -> str:
    """Normalize a datetime to UTC RFC 3339 with uppercase Z.

    Raises:
        ValueError: If the datetime is timezone-naive.
    """
    if value.tzinfo is None:
        raise ValueError(
            "timezone-naive datetimes are not permitted in canonical JSON v0.1; "
            "provide a timezone-aware datetime"
        )
    utc_dt = value.astimezone(UTC)
    # Replace +00:00 suffix with Z for canonical RFC 3339 output.
    return utc_dt.isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Canonical serialization core
# ---------------------------------------------------------------------------


def _canonical_json_str(value: Any) -> str:
    """Produce the canonical JSON string for a pre-normalized value.

    The input MUST already be normalized (only None, bool, str, int, list,
    dict with string keys). This function handles recursive key sorting
    and compact serialization.

    Implementation detail: We use ``json.dumps`` with ``sort_keys=True``
    for dicts and ``separators=(",", ":")`` for compact output. The
    recursive sort ensures deterministic output independent of insertion
    order.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_json_text(value: Any) -> str:
    """Serialize ``value`` to canonical JSON text (ZADC Canonical JSON v0.1).

    The input is first normalized (type-checked and datetime-converted),
    then serialized with recursively sorted keys and compact separators.

    Args:
        value: A value to serialize. Must be composed of ``None``, ``bool``,
            ``str``, ``int``, ``list``, string-keyed ``dict``, and
            timezone-aware ``datetime`` after any model conversion.

    Returns:
        Canonical JSON text string (no trailing newline).

    Raises:
        CanonicalJSONTypeError: If the value contains floats, Decimal,
            bytes, sets, tuples, non-string keys, or arbitrary objects.
        ValueError: If a timezone-naive datetime is encountered.
    """
    normalized = _normalize_value(value)
    return _canonical_json_str(normalized)


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize ``value`` to canonical JSON bytes (ZADC Canonical JSON v0.1).

    Equivalent to ``canonical_json_text(value).encode("utf-8")``.
    The output is UTF-8 encoded with no BOM and no trailing newline.

    Args:
        value: See :func:`canonical_json_text`.

    Returns:
        Canonical JSON bytes (UTF-8, no BOM, no trailing newline).

    Raises:
        CanonicalJSONTypeError: See :func:`canonical_json_text`.
        ValueError: See :func:`canonical_json_text`.
    """
    return canonical_json_text(value).encode("utf-8")


# Import here to avoid module-level circular import issues.

__all__ = [
    "canonical_json_bytes",
    "canonical_json_text",
    "CanonicalJSONTypeError",
]
