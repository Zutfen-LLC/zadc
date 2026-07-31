# ZADC Public API — A1 Foundation

This document describes the public API surface for the ZADC A1 common
artifact foundation.

## Overview

The A1 foundation provides the reusable canonical-artifact substrate
shared by all future ZADC artifacts. It does NOT implement concrete
artifact body models (packet, completion report, etc.), workflow bundles,
lifecycle state, policy evaluation, Git/GitHub reconciliation, consumer
renderers, signing, or integrations.

## Types

### ActorType

```python
ActorType = Literal["human", "agent", "ci", "validator", "service"]
```

Valid actor types per architecture section 6.

### ArtifactType

```python
ArtifactType = Literal[
    "packet", "completion_report", "certification_manifest",
    "review_report", "decision_record", "workflow_bundle",
    "evidence_artifact", "observation",
]
```

Valid artifact types per architecture section 11 (expanded with
`evidence_artifact` and `observation`).

### Sha256Digest

Annotated `str` validated as `sha256:` followed by exactly 64 lowercase hex
characters.

### GitSha

Annotated `str` validated as exactly 40 lowercase hex characters.

## Models

All models are strict (`extra=forbid`), frozen (immutable), and validated
at construction.

### ArtifactEnvelope

The common envelope shared by all ZADC artifacts (architecture section 10).

Fields:
- `schema` (alias for `schema_uri`): Always `https://schemas.zutfen.com/zadc/0.1/artifact.schema.json`
- `contract_version`: Always `0.1.0`
- `artifact_type`: One of `ArtifactType`
- `artifact_id`: Stable identifier (validated)
- `created_at`: Timezone-aware datetime (normalized to UTC)
- `producer`: `ProducerIdentity`
- `project_id`: Stable identifier
- `slice_id`: Stable identifier
- `slice_instance_id`: Stable identifier
- `policy`: `PolicyReference`
- `provenance`: `Provenance`

No status/authority field is declared — the envelope carries no
authorization, verification, approval, merge-worthiness, or merge claim.

### ProducerIdentity

- `actor_type`: One of `ActorType`
- `actor_id`: Stable identifier
- `run_id`: Optional stable identifier
- `model`: Optional string
- `provider`: Optional string

### PolicyReference

- `policy_id`: Stable identifier
- `policy_source_sha`: `GitSha` (40 lowercase hex)
- `policy_digest`: `Sha256Digest`

### Provenance

- `parent_artifact_ids`: List of stable identifiers (empty for roots)
- `content_digest`: Optional `Sha256Digest` (absent before sealing)

## Canonical JSON

### canonical_json_bytes(value) → bytes

Serialize `value` to ZADC Canonical JSON v0.1 bytes (UTF-8, no BOM, no
trailing newline).

### canonical_json_text(value) → str

Serialize `value` to ZADC Canonical JSON v0.1 text.

See [docs/canonical-json-v0.1.md](canonical-json-v0.1.md) for the full profile.

## Digests

### compute_content_digest(envelope) → str

Compute the SHA-256 content digest for an artifact envelope. The digest is
`sha256:` followed by 64 lowercase hex characters. Computed over canonical
JSON bytes with `provenance.content_digest` set to `None` (excluded).

Never mutates the input. Safe to call on both sealed and unsealed envelopes.

### seal_artifact(envelope) → ArtifactEnvelope

Return a new immutable copy of the envelope with `content_digest` set to
the computed digest. The input is never mutated. Idempotent — re-sealing
an unmodified sealed envelope produces the same digest.

### verify_content_digest(envelope) → str

Verify that the stored `content_digest` matches the recomputed digest.
Uses constant-time comparison (`hmac.compare_digest`). Never repairs.

Raises:
- `DigestMissingError`: If `content_digest` is `None` (not sealed).
- `DigestMismatchError`: If stored digest does not match recomputed digest.

## Errors

### DigestError

Base class for all digest-related errors.

### DigestMissingError

The envelope has not been sealed (`content_digest` is `None`).

### DigestMismatchError

The stored digest does not match the recomputed digest. Carries `stored`
and `expected` attributes.

## Typical workflow

```python
from datetime import datetime, timezone
from zadc import (
    ArtifactEnvelope,
    ProducerIdentity,
    PolicyReference,
    Provenance,
    seal_artifact,
    verify_content_digest,
    canonical_json_text,
)

# 1. Construct
envelope = ArtifactEnvelope(
    artifact_type="packet",
    artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
    created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc),
    producer=ProducerIdentity(
        actor_type="human",
        actor_id="zutfen:human:eric",
    ),
    project_id="zutfen:project:zadc",
    slice_id="ZADC-001A",
    slice_instance_id="ZADC-001A1",
    policy=PolicyReference(
        policy_id="zutfen:zadc-policy:standard@0.1.0",
        policy_source_sha="a" * 40,
        policy_digest="sha256:" + "b" * 64,
    ),
    provenance=Provenance(parent_artifact_ids=[]),
)

# 2. Seal
sealed = seal_artifact(envelope)
assert sealed.provenance.content_digest is not None

# 3. Serialize
data = sealed.model_dump(mode="json", by_alias=True)
canonical = canonical_json_text(data)

# 4. Reload (from JSON)
import json
reloaded = ArtifactEnvelope.model_validate(json.loads(canonical))

# 5. Verify
verify_content_digest(reloaded)  # raises if missing or mismatched
```

## JSON Schema

A Draft 2020-12 JSON Schema is generated at
`schemas/0.1/artifact-envelope.schema.json`. The schema is reproducibly
generated via `scripts/export_schemas.py` and is byte-stable.
