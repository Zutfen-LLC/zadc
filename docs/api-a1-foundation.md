# ZADC Public API — A1 Foundation

This document describes the public API surface for the ZADC A1 common
artifact foundation.

## Overview

The A1 foundation provides the reusable canonical-artifact substrate
shared by all future ZADC artifacts. It does NOT implement concrete
artifact body models, workflow bundles, lifecycle state, policy evaluation,
Git/GitHub reconciliation, consumer renderers, signing, or integrations.

## Types

### ActorType

```python
ActorType = Literal["human", "agent", "ci", "validator", "service"]
```

### ArtifactType

```python
ArtifactType = Literal[
    "packet", "completion_report", "certification_manifest",
    "review_report", "decision_record", "workflow_bundle",
    "evidence_artifact", "observation",
]
```

### GlobalId

URI-shaped global identifier for artifact, project, actor, run, and policy
references following the ZADC GlobalId v0.1 profile:

- **Scheme**: Canonical lowercase ASCII `[a-z][a-z0-9+.-]*`
- **Separator**: Colon `:`
- **Scheme-specific part**: At least one ASCII RFC 3986 URI character
  (unreserved/reserved/pct-encoded). Raw whitespace, controls, Unicode,
  backslashes, quotes, and angle brackets are **rejected**, not normalized.
- **Percent escapes**: Valid `%HH` sequences using uppercase hex only.
- **Unicode**: Raw Unicode is rejected; use explicit percent-encoded UTF-8
  when a future scheme permits it.
- **UUID URNs**: Must be exactly `urn:uuid:` followed by the canonical
  lowercase hyphenated UUID text (e.g.
  `urn:uuid:00000000-0000-0000-0000-000000000001`). Malformed, uppercase-prefix,
  uppercase-hex, unhyphenated, braced, or otherwise noncanonical UUID URNs
  are rejected.

This validator does NOT make network calls or attempt scheme-specific
resource resolution.

### SliceId

Human-friendly bounded identifier for slice and slice-instance references.
Grammar: `[A-Z0-9]([A-Z0-9-]*[A-Z0-9])?` — uppercase letters, digits, and
hyphens. Must start and end with an alphanumeric character. Rejects all
Unicode category C characters.

### Sha256Digest

`sha256:` followed by exactly 64 lowercase hex characters.

### GitSha

Exactly 40 lowercase hex characters.

## Models

All models are strict (`extra=forbid`, `strict=True`), frozen (immutable),
and validated at construction. Provenance collections use immutable tuples
internally.

### ArtifactEnvelope

The common envelope shared by all ZADC artifacts (architecture section 10).

**Required fields** (FIX2-A):
- `schema` (alias for `schema_uri`): MUST be exactly
  `https://schemas.zutfen.com/zadc/0.1/artifact.schema.json`. Emits a JSON
  Schema `const` entry. No default — callers must supply it explicitly.
- `contract_version`: MUST be exactly `0.1.0`. Emits a JSON Schema `const`
  entry. No default — callers must supply it explicitly.

Other fields:
- `artifact_type`, `artifact_id`, `created_at`, `producer`, `project_id`
- `slice_id`, `slice_instance_id`
- `policy`: `PolicyReference`
- `provenance`: `Provenance`

`created_at` accepts a timezone-aware `datetime` or a ZADC Timestamp v0.1
string. The ZADC Timestamp v0.1 grammar is:

    YYYY-MM-DDTHH:MM:SS[.ffffff](Z|+HH:MM|-HH:MM)

with uppercase `T` and `Z`. Fractional seconds: 1–6 digits only (Python
datetime microsecond precision). Leap seconds (`:60`) and unknown offset
(`-00:00`) are rejected in v0.1. Rejects int, float, Decimal, bool, bytes,
naive datetime, date, and all `datetime.fromisoformat` over-acceptance
examples (spaces, basic forms, week dates, ordinal dates, offsets without
colon, lowercase t/z, trailing data).

The generated JSON Schema emits both `format: date-time` and the exact
ZADC Timestamp v0.1 `pattern` for `created_at`.

### Provenance

- `parent_artifact_ids`: **Required** (FIX2-A). Immutable tuple of `GlobalId`
  (accepted as list/tuple). Root artifacts must explicitly supply an empty
  array/tuple. The generated JSON Schema marks this field as `required`.
- `content_digest`: Optional `Sha256Digest` (absent before sealing)

## Canonical JSON

`canonical_json_bytes(value)` and `canonical_json_text(value)` accept
Pydantic `BaseModel` instances directly and produce deterministic canonical
output. See [docs/canonical-json-v0.1.md](canonical-json-v0.1.md).

## Digests

### compute_content_digest(envelope) → str

SHA-256 of canonical bytes with `provenance.content_digest` **removed
entirely** from the payload. Never mutates input.

### seal_artifact(envelope) → ArtifactEnvelope

Returns a new validated envelope with `content_digest` set. Uses validated
reconstruction (`model_validate`), not unvalidated `model_copy(update=...)`.
Idempotent.

### verify_content_digest(envelope) → str

Verifies stored digest via `hmac.compare_digest`. Never repairs.
Raises `DigestMissingError` or `DigestMismatchError`.

## Schema Derivation

The JSON Schema is derived from `ArtifactEnvelope.model_json_schema()` with
deterministic post-processing. ALL business constraints — const values,
required fields, enums, GlobalId patterns, UUID conditionals (if/then),
timestamp ranges, -00:00 exclusion — originate from the model's Pydantic
type metadata and custom `__get_pydantic_json_schema__` hooks.

The exporter adds only stable document metadata (`$schema`, `$id`, `title`,
`description`) and deterministic key ordering. It does NOT inject or modify
any business constraint.

Independent validation uses `Draft202012Validator` with an explicit
`FormatChecker` (backed by `rfc3339-validator`) so the committed schema
independently rejects:
- Malformed and lowercase percent escapes
- Noncanonical UUID URNs (via if/then conditional)
- Leap seconds (:60), invalid numeric time/offset ranges
- `-00:00` (via `not` constraint)
- Invalid calendar dates (via `format: date-time` + FormatChecker)

## Typical workflow

```python
from datetime import datetime, timezone
from zadc import (
    ArtifactEnvelope, ProducerIdentity, PolicyReference, Provenance,
    seal_artifact, verify_content_digest, canonical_json_text,
)

# 1. Construct
envelope = ArtifactEnvelope(
    schema="https://schemas.zutfen.com/zadc/0.1/artifact.schema.json",
    contract_version="0.1.0",
    artifact_type="packet",
    artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
    created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc),
    producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:eric"),
    project_id="zutfen:project:zadc",
    slice_id="ZADC-001A",
    slice_instance_id="ZADC-001A1",
    policy=PolicyReference(
        policy_id="zutfen:zadc-policy:standard@0.1.0",
        policy_source_sha="a" * 40,
        policy_digest="sha256:" + "b" * 64,
    ),
    provenance=Provenance(parent_artifact_ids=()),
)

# 2. Seal
sealed = seal_artifact(envelope)

# 3. Direct canonicalization (no manual dump needed)
text = canonical_json_text(sealed)

# 4. Reload and verify
import json
reloaded = ArtifactEnvelope.model_validate(json.loads(text))
verify_content_digest(reloaded)
```
