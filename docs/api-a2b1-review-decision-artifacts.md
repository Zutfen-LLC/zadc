# ZADC Public API — A2B1 Review and Decision Artifacts

This document describes the public API surface added by A2B1 on top of the
A1 common artifact foundation (see [docs/api-a1-foundation.md](api-a1-foundation.md))
and the A2A execution/evidence artifacts (see
[docs/api-a2a-execution-evidence-artifacts.md](api-a2a-execution-evidence-artifacts.md)).

## Overview

A2B1 implements two concrete ZADC artifact bodies: **ReviewReport** and
**DecisionRecord**. Each extends `ArtifactEnvelope` and narrows
`artifact_type` to its own `Literal`. All models remain strict
(`extra="forbid"`, `strict=True`), frozen, and validated at construction.

A2B1 preserves a strict distinction between two different kinds of
artifact:

- **`ReviewReport`** records a **reviewer's judgment** — what a reviewer
  (human or agent) examined and concluded. It is evidence of judgment, not
  authority.
- **`DecisionRecord`** records an **authenticated human decision claim** —
  what a human decision-maker claims to have decided. A structurally valid
  `DecisionRecord` does not, by itself, authenticate that human identity or
  confer merge authorization.

Neither artifact computes finding-closure policy, blocking thresholds,
merge eligibility, or accepted-risk policy evaluation. See
[Trust limitations](#trust-limitations) below.

## Shared contract enums (`zadc.types`)

- **`FindingStatus`** — `open`, `resolved`, `accepted_risk`, `invalid`,
  `superseded`.
- **`ReviewerRecommendation`** — `green_for_merge`, `green_for_review`,
  `red`, `blocked`, `inconclusive`. Judgment only — never a merge
  authorization.
- **`DecisionType`** — `request_changes`, `approve_for_merge`, `reject`,
  `accept_risk`, `supersede`.
- **`FindingLocationType`** — `file`, `artifact`, `general`: the
  discriminant for the typed finding-location union.

## ReviewReport

A reviewer's structured judgment of an exact subject. Extends
`ArtifactEnvelope` with `artifact_type: Literal["review_report"]`.

| Field | Type | Notes |
|---|---|---|
| `packet_id` | `GlobalId` | |
| `review_id` | `GlobalId` | must equal the envelope `artifact_id` |
| `reviewer` | `ReviewerIdentity` | `actor_type` (`human`\|`agent`), `actor_id`, optional `run_id`/`model`/`provider`; must match the envelope `producer`'s `actor_type` and `actor_id` |
| `independence` | `ReviewIndependence` | `executor_actor_id`, `satisfied`; when `satisfied` is `True`, `reviewer.actor_id` must differ from `executor_actor_id` |
| `subject` | `ReviewSubject` | `repository_id`, `review_subject_sha`, `packet_digest`, `certification_manifest_ids` (duplicate-free) |
| `inputs_reviewed` | `ReviewInputs` | `diffs: tuple[EvidenceReference, ...]`, `files: tuple[ReviewedFile, ...]`, `evidence_artifacts: tuple[ArtifactReference, ...]` |
| `findings` | `tuple[Finding, ...]` | unique `finding_id` values |
| `limitations` | `tuple[ConstrainedText, ...]` | |
| `reviewer_recommendation` | `ReviewerRecommendation` | judgment only |

### Supporting models

- **`ReviewerIdentity`** — distinct from `ProducerIdentity`: `actor_type`
  is narrowed to `human`\|`agent` (a reviewer is never `ci`, `validator`,
  or `service`). `model`/`provider` are `Optional[ConstrainedText]`
  (bounded prose, not bare `str`).
- **`ReviewIndependence`** — records the reviewer's independence claim
  relative to the executing actor. This is an **internal-consistency
  check only** — it does not authenticate the reviewer or prove trusted
  independence.
- **`ReviewSubject`** — the claimed exact subject. Does not inspect Git,
  retrieve evidence, or prove the listed inputs were actually reviewed.
- **`ReviewedFile`** — `path`, optional `start_line`/`end_line`. `end_line`
  must not be present without `start_line`; when both are present,
  `end_line` must not precede `start_line`.
- **`ReviewInputs`** — the diffs, files, and evidence artifacts a review
  claims to cover.
- **`Finding`** — `finding_id` (`StableId`), `severity` (`FindingSeverity`),
  `status` (`FindingStatus`), `location` (typed union, see below),
  `statement`, `rationale`, `resolution_refs: tuple[ArtifactReference, ...]`.
  `status="resolved"` and `status="accepted_risk"` each independently
  require at least one resolution reference — enforced by both the model
  and the generated schema (see
  [Schema-expressible invariants](#schema-expressible-invariants)). This
  model does not verify that a resolution reference actually resolves or
  closes the finding.

### Typed finding-location union

`FindingLocation` is a Pydantic discriminated union on `location_type`:

- **`FileFindingLocation`** (`location_type="file"`): `path`, optional
  `start_line`/`end_line` (same range rule as `ReviewedFile`).
- **`ArtifactFindingLocation`** (`location_type="artifact"`):
  `artifact_id`. Does not perform repository lookup or cross-artifact
  reference resolution.
- **`GeneralFindingLocation`** (`location_type="general"`): `description`.

Each variant is strict (`extra="forbid"`), so a payload carrying a field
from another variant (e.g. `artifact_id` alongside `location_type="file"`)
is rejected both at runtime and by the generated schema's discriminated
`oneOf`. This model does not verify that a referenced file or line range
exists.

## DecisionRecord

An authenticated human decision claim. Extends `ArtifactEnvelope` with
`artifact_type: Literal["decision_record"]`.

| Field | Type | Notes |
|---|---|---|
| `decision_id` | `GlobalId` | must equal the envelope `artifact_id` |
| `decided_by` | `HumanDecisionIdentity` | `actor_type="human"`, `actor_id`; the envelope `producer` must have `actor_type="human"` and `actor_id` equal to `decided_by.actor_id` |
| `decided_at` | `Timestamp` | |
| `subject` | `DecisionSubject` | see below |
| `decision` | `DecisionType` | |
| `accepted_risks` | `tuple[AcceptedRisk, ...]` | non-empty iff `decision="accept_risk"`; empty otherwise; unique `finding_id` values |
| `supersedes_decision_ref` | `Optional[ArtifactReference]` | non-null iff `decision="supersede"`; null otherwise; must not reference this artifact's own `artifact_id` |
| `conditions` | `tuple[ConstrainedText, ...]` | |
| `rationale` | `ConstrainedText` | |

### Supporting models

- **`HumanDecisionIdentity`** — `actor_type` fixed to `Literal["human"]`;
  `actor_id`. Records the claimed identity only — authenticating it
  against a trusted identity provider is deferred to a later validation
  slice.
- **`DecisionSubject`** — `repository_id`, `pull_request` (`PositiveInt`),
  `decision_subject_sha`, `current_pr_head_sha_observed`,
  `review_report_ids` (duplicate-free `tuple[GlobalId, ...]`),
  `certification_manifest_ids` (duplicate-free). `decision_subject_sha`
  and `current_pr_head_sha_observed` are **not** required to match at
  construction — freshness and live-head reconciliation are deferred.
- **`AcceptedRisk`** — `finding_id` (`StableId`), `rationale`, `scope`,
  optional `expires_at`. When present, `expires_at` must be later than the
  enclosing `DecisionRecord.decided_at` (enforced by `DecisionRecord`,
  since `expires_at` is compared against a sibling artifact-level field —
  see [Runtime-only invariants](#runtime-only-invariants)).

A structurally valid `DecisionRecord` does **not**, by itself, authenticate
its human identity and does **not** confer merge authorization until a
later trusted validator binds the identity and verifies policy and live
repository state.

## Schema-expressible invariants

The following conditional gates are model-owned and appear in the
generated JSON Schema as `allOf`/`if`/`then` blocks — independently
verified against the raw schema in `tests/test_a2b1_schema_export.py`,
proving both the missing-field and explicit-`null` cases separately where
applicable:

- **`Finding`**: `status="resolved"` → `resolution_refs` has `minItems: 1`
  (one `if`/`then` block); `status="accepted_risk"` → `resolution_refs` has
  `minItems: 1` (a second, independent `if`/`then` block).
- **`DecisionRecord`**: `decision="accept_risk"` → `accepted_risks` has
  `minItems: 1`; every other `decision` → `accepted_risks` has
  `maxItems: 0`. `decision="supersede"` → `supersedes_decision_ref` is
  `required` and `"not": {"type": "null"}`; every other `decision` →
  `supersedes_decision_ref` has `"type": "null"`. Each of these four
  conditions is its own independent `if`/`then` block.

## Runtime-only invariants

The following invariants have no standard JSON Schema (Draft 2020-12)
vocabulary and are enforced only by the Python models' `model_validator`s
— not by the generated schemas:

**Comparisons between two arbitrary sibling or cross-object values:**

- `ReviewReport.review_id` must equal the envelope `artifact_id`.
- `ReviewReport.reviewer.actor_id`/`actor_type` must match the envelope
  `producer`'s `actor_id`/`actor_type`.
- `ReviewReport.independence.satisfied=True` requires
  `reviewer.actor_id != independence.executor_actor_id`.
- `ReviewedFile`/`FileFindingLocation`: `end_line` must not precede
  `start_line` (the *presence* dependency — `end_line` requires
  `start_line` — is a simple single-field check with no schema hook
  attached in this slice; both halves are runtime-only here).
- `DecisionRecord.decision_id` must equal the envelope `artifact_id`.
- `DecisionRecord`: the envelope `producer` must have `actor_type="human"`
  and `actor_id` equal to `decided_by.actor_id`.
- `DecisionRecord.supersedes_decision_ref.artifact_id` must not equal this
  artifact's own `artifact_id`.
- `AcceptedRisk.expires_at` must be later than the enclosing
  `DecisionRecord.decided_at` — a comparison against a field on a
  different, enclosing object. Expiration ordering is runtime-only and
  unavailable to standard JSON Schema.

**Cross-item uniqueness by field** (JSON Schema's `uniqueItems` compares
whole array items, not a single field within each item):

- `ReviewSubject.certification_manifest_ids` must be duplicate-free.
- `ReviewReport.findings[].finding_id` must be unique across the report.
- `DecisionSubject.review_report_ids` and `.certification_manifest_ids`
  must each be duplicate-free.
- `DecisionRecord.accepted_risks[].finding_id` must be unique within the
  decision record.

All of the above are covered by direct unit tests (constructing the model
and asserting `ValidationError`), independent of schema validation. See
`docs/api-a2a-execution-evidence-artifacts.md#runtime-only-invariants` for
the analogous A2A inventory.

## Authority boundaries and internal-consistency checks

These artifacts preserve the distinction between reviewer **judgment** and
authenticated human **authority**:

- `ReviewReport.reviewer`/`independence` checks establish **internal
  consistency only** (the reviewer claims to be the envelope producer; the
  independence claim is self-consistent). They do not authenticate the
  reviewer's identity or prove trusted independence.
- `ReviewReport.reviewer_recommendation` is judgment only and must never be
  represented as merge authorization.
- `DecisionRecord`'s producer/`decided_by` check establishes that the
  envelope producer consistently claims to be the same human as
  `decided_by`. It does **not** authenticate that human identity against a
  trusted identity provider, and a structurally valid `DecisionRecord`
  does **not** confer merge authorization — a later trusted validator must
  bind the identity and verify policy and live repository state.

## Digest sealing, canonicalization, and schema export

`seal_artifact`, `compute_content_digest`, and `verify_content_digest`
operate polymorphically and require no artifact-specific code — they
already preserve the concrete runtime class (`ReviewReport`,
`DecisionRecord`) and cover every body field, top-level or nested, exactly
as for the five A2A artifacts (see
[docs/api-a2a-execution-evidence-artifacts.md#digest-sealing-across-concrete-artifacts-a2a-09](api-a2a-execution-evidence-artifacts.md)).

`scripts/export_schemas.py`'s data-driven spec list gained two entries,
producing:

```text
schemas/0.1/review-report.schema.json
schemas/0.1/decision-record.schema.json
```

with no change to the exporter's mutation surface (still limited to
document metadata and deterministic key ordering) and no change to any of
the six previously committed schema files.

## Construction and sealing example

```python
from datetime import datetime, timezone
from zadc import (
    CONTRACT_VERSION, SCHEMA_ID,
    PolicyReference, ProducerIdentity, Provenance,
    ReviewReport, ReviewerIdentity, ReviewIndependence, ReviewSubject,
    ReviewInputs, ReviewedFile, Finding, FileFindingLocation,
    DecisionRecord, HumanDecisionIdentity, DecisionSubject, AcceptedRisk,
    seal_artifact, verify_content_digest, canonical_json_text,
)

review = ReviewReport(
    schema=SCHEMA_ID,
    contract_version=CONTRACT_VERSION,
    artifact_type="review_report",
    artifact_id="urn:uuid:00000000-0000-0000-0000-000000000201",
    created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc),
    producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:reviewer"),
    project_id="zutfen:project:zadc",
    slice_id="ZADC-001A2B1",
    slice_instance_id="ZADC-001A2B11",
    policy=PolicyReference(
        policy_id="zutfen:zadc-policy:standard@0.1.0",
        policy_source_sha="a" * 40,
        policy_digest="sha256:" + "b" * 64,
    ),
    provenance=Provenance(parent_artifact_ids=()),
    packet_id="urn:uuid:00000000-0000-0000-0000-000000000001",
    review_id="urn:uuid:00000000-0000-0000-0000-000000000201",
    reviewer=ReviewerIdentity(actor_type="human", actor_id="zutfen:human:reviewer"),
    independence=ReviewIndependence(executor_actor_id="zutfen:agent:hermes", satisfied=True),
    subject=ReviewSubject(
        repository_id="github:Zutfen-LLC/zadc",
        review_subject_sha="b" * 40,
        packet_digest="sha256:" + "c" * 64,
        certification_manifest_ids=(),
    ),
    inputs_reviewed=ReviewInputs(
        diffs=(), files=(ReviewedFile(path="src/zadc/models/packet.py"),), evidence_artifacts=(),
    ),
    findings=(
        Finding(
            finding_id="F-1", severity="minor", status="open",
            location=FileFindingLocation(location_type="file", path="src/zadc/models/packet.py"),
            statement="Minor style nit", rationale="Not blocking", resolution_refs=(),
        ),
    ),
    limitations=(), reviewer_recommendation="green_for_review",
)

sealed_review = seal_artifact(review)
verify_content_digest(sealed_review)

decision = DecisionRecord(
    schema=SCHEMA_ID, contract_version=CONTRACT_VERSION,
    artifact_type="decision_record",
    artifact_id="urn:uuid:00000000-0000-0000-0000-000000000202",
    created_at=datetime(2026, 7, 31, 13, 0, 0, tzinfo=timezone.utc),
    producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:decider"),
    project_id="zutfen:project:zadc",
    slice_id="ZADC-001A2B1", slice_instance_id="ZADC-001A2B11",
    policy=PolicyReference(
        policy_id="zutfen:zadc-policy:standard@0.1.0",
        policy_source_sha="a" * 40, policy_digest="sha256:" + "b" * 64,
    ),
    provenance=Provenance(parent_artifact_ids=()),
    decision_id="urn:uuid:00000000-0000-0000-0000-000000000202",
    decided_by=HumanDecisionIdentity(actor_type="human", actor_id="zutfen:human:decider"),
    decided_at=datetime(2026, 7, 31, 13, 0, 0, tzinfo=timezone.utc),
    subject=DecisionSubject(
        repository_id="github:Zutfen-LLC/zadc", pull_request=42,
        decision_subject_sha="b" * 40, current_pr_head_sha_observed="b" * 40,
        review_report_ids=(review.artifact_id,), certification_manifest_ids=(),
    ),
    decision="approve_for_merge",
    accepted_risks=(), supersedes_decision_ref=None,
    conditions=(), rationale="All mandatory lanes passed and findings are non-blocking",
)

sealed_decision = seal_artifact(decision)
verify_content_digest(sealed_decision)
```

## Trust limitations

This slice does **not** implement:

- `WorkflowBundle` or a global discriminated artifact union across all
  artifact types;
- derived lifecycle state, finding-closure policy, blocking-threshold
  evaluation, or merge-eligibility derivation;
- authentication of reviewer or human decision-maker identity against a
  trusted identity provider;
- proof of reviewer independence beyond the internal-consistency check
  described above;
- accepted-risk policy evaluation, or reconciliation of
  `decision_subject_sha` against a live PR head;
- cross-artifact referential-integrity validation (e.g. verifying that a
  `review_report_ids` entry resolves to a sealed `ReviewReport` with a
  matching digest);
- Git ancestry/diff inspection, GitHub/CI API adapters, or remote evidence
  retrieval;
- CLI validation commands or consumer-specific renderers;
- Engram/Flowstate integration or cryptographic signing.

These remain scoped to A2B2 and later slices per
[docs/roadmap.md](roadmap.md).
