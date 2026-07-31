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
references. Must have a syntactically valid URI scheme (e.g. `urn:uuid:`,
`zutfen:`, `github:`). Rejects all Unicode category C characters. `urn:uuid:`
identifiers must use canonical lowercase hex.

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

Fields:
- `schema` (alias for `schema_uri`)
- `contract_version`: Always `0.1.0`
- `artifact_type`, `artifact_id`, `created_at`, `producer`, `project_id`
- `slice_id`, `slice_instance_id`
- `policy`: `PolicyReference`
- `provenance`: `Provenance`

`created_at` accepts a timezone-aware `datetime` or an RFC 3339 string.
Rejects int, float, Decimal, bool, bytes, naive datetime, and date.

### Provenance

- `parent_artifact_ids`: Immutable tuple of `GlobalId` (accepted as list/tuple)
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
deterministic post-processing. It is NOT hand-written. Constraints (patterns,
enums, required fields) come from the model's Pydantic metadata.

## Typical workflow

```python
from datetime import datetime, timezone
from zadc import (
    ArtifactEnvelope, ProducerIdentity, PolicyReference, Provenance,
    seal_artifact, verify_content_digest, canonical_json_text,
)

# 1. Construct
envelope = ArtifactEnvelope(
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
