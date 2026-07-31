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

## No-float rule

Floating-point representations vary across languages, platforms, and library
versions, making them unsuitable for deterministic digest computation. The
no-float rule is intentional cross-language digest hardening for v0.1.

Integer quantities and string-encoded values should be used instead. This
rule may be revisited in a future contract version if a deterministic float
encoding profile is adopted.

## Public API

```python
from zadc import canonical_json_bytes, canonical_json_text

# Returns canonical JSON as UTF-8 bytes (no BOM, no trailing newline)
b = canonical_json_bytes({"b": 1, "a": 2})
# b'{"a":2,"b":1}'

# Returns canonical JSON as a string
s = canonical_json_text({"b": 1, "a": 2})
# '{"a":2,"b":1}'
```

## Error handling

If a value contains a type not permitted in canonical JSON, a
`CanonicalJSONTypeError` (subclass of `TypeError`) is raised with a
descriptive message. The error never echoes the full artifact — only the
type name and a short hint are included.

## Determinism guarantees

- **Insertion-order independence**: Dicts with the same key-value pairs
  produce identical output regardless of insertion order.
- **PYTHONHASHSEED independence**: Output is identical across processes
  with different `PYTHONHASHSEED` values.
- **Idempotence**: Re-serializing the parsed output produces identical bytes.
