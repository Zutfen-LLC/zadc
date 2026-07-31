# ZADC Canonical JSON v0.1

This document defines the ZADC Canonical JSON serialization profile, which
is used for content digest computation across all ZADC artifacts.

## Profile rules

1. **Encoding**: UTF-8 bytes, no BOM, no trailing newline.
2. **Object keys**: Recursively sorted by Unicode code-point order (ascending).
3. **Separators**: Compact — `","` and `":"` with no whitespace.
4. **Unicode**: Direct UTF-8 output with valid JSON escaping
   (`ensure_ascii=False`). Characters are NOT `\u00XX`-escaped.
5. **Data types**: After model conversion, only `None` (→ `null`), `bool`,
   `str`, `int`, `list`, and string-keyed `dict` are permitted.
6. **Rejected types**: `float` (including `-0.0`, `NaN`, `Infinity`),
   `Decimal`, `bytes`, `set`, `frozenset`, `tuple`, non-string keys,
   and arbitrary objects.
7. **Datetime normalization**: All timezone-aware datetimes are normalized
   to UTC and serialized as RFC 3339 strings with uppercase `Z`.
8. **Determinism**: Output is idempotent and independent of insertion order
   and `PYTHONHASHSEED`.
9. **Pydantic models**: Accepted directly and converted via a fixed dump
   profile: `mode="json"`, `by_alias=True`, `exclude_none=False`,
   `exclude_defaults=False`, `exclude_unset=False`.

## Digest field exclusion

The content digest is computed over canonical JSON bytes with
`provenance.content_digest` **removed entirely** from the payload (not
set to `null`). The `content_digest` key is completely absent from the
digest-input bytes.

## Direct model canonicalization

Pydantic `BaseModel` instances are accepted directly by
`canonical_json_text` and `canonical_json_bytes`. Callers do not need to
manually dump the model first:

```python
from zadc import ArtifactEnvelope, seal_artifact, canonical_json_text

sealed = seal_artifact(envelope)
text = canonical_json_text(sealed)  # direct model → canonical JSON
```

The fixed dump profile ensures construction history does not affect output:
omitted defaults and explicitly supplied defaults/nulls canonicalize identically.

## No-float rule

Floating-point representations vary across languages, platforms, and library
versions, making them unsuitable for deterministic digest computation. The
no-float rule is intentional cross-language digest hardening for v0.1.

## Public API

```python
from zadc import canonical_json_bytes, canonical_json_text

# Direct model conversion
b = canonical_json_bytes(sealed_envelope)
s = canonical_json_text(sealed_envelope)

# Plain dict conversion
b = canonical_json_bytes({"b": 1, "a": 2})
# b'{"a":2,"b":1}'
```

## Error handling

If a value contains a type not permitted in canonical JSON, a
`CanonicalJSONTypeError` (subclass of `TypeError`) is raised with a
descriptive message.
