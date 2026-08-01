# ZADC Public API — A2A Execution and Evidence Artifacts

This document describes the public API surface added by A2A on top of the
A1 common artifact foundation (see
[docs/api-a1-foundation.md](api-a1-foundation.md)).

## Overview

A2A implements the first concrete ZADC artifact bodies: **Packet**,
**CompletionReport**, **CertificationManifest**, **EvidenceArtifact**, and
**Observation**. Each extends `ArtifactEnvelope` and narrows
`artifact_type` to its own `Literal`. All models remain strict
(`extra="forbid"`, `strict=True`), frozen, and validated at construction.

A2A does **not** implement workflow lifecycle derivation, policy
evaluation, review, human decisions, provider adapters, or rendering. See
[Trust limitations](#trust-limitations) below.

## Reusable shared types (`zadc.types`)

- **`Timestamp`** — the ZADC Timestamp v0.1 field type for *nested*
  artifact timestamps (e.g. `PacketAuthorization.authorized_at`,
  `LaneResult.started_at`). Enforces the exact same grammar, calendar
  validity, UTC normalization, and uppercase-`Z` serialization as
  `ArtifactEnvelope.created_at` — the envelope field's own validator was
  refactored to share this logic rather than duplicate it, with no
  behavior change.
- **`ConstrainedText`** — bounded (1–20000 char) prose text. Rejects
  empty/whitespace-only values, leading/trailing whitespace, and Unicode
  control/format/surrogate/private-use/unassigned characters other than
  internal newline/tab.
- **`StableId`** — a bounded human-assigned identifier grammar
  (`[A-Za-z0-9][A-Za-z0-9._-]*`), used for `requirement_id` and `lane_id`.
- **`MediaType`** — a simplified RFC 6838 `type/subtype` MIME grammar.
- **`GitHubName`** — a GitHub owner/repository name segment.
- **`RefName`** — a Git ref/branch name (permits internal `/`).
- **`coerce_tuple`** — the shared before-validator that normalizes
  JSON-array/Python-list input into an immutable tuple, reused across
  every collection field instead of a per-model validator.

### Shared contract enums

`EpistemicStatus`, `MismatchPolicy`, `ExactSubjectPolicy`,
`FindingSeverity`, `ExecutorRecommendation`, `SubjectKind`,
`LaneClassification`, `LaneConclusion`, `CertificationResult`,
`EvidenceAvailability`, `ObservationSourceType` — all `Literal` aliases
that emit exact JSON Schema `enum` entries with no runtime-only values.

## Shared supporting models (`zadc.models`)

- **`ArtifactReference`** — `artifact_id` + `content_digest`: a reference
  to another *canonical ZADC artifact* by identity and sealed digest. Used
  by `Packet.supersedes`.
- **`EvidenceReference`** — `artifact_id`, `media_type`, `digest`,
  `location`: a lightweight, denormalized pointer to an *external* evidence
  payload. Used by `CertificationManifest.evidence`, `LaneResult.evidence_refs`,
  `ExecutorClaim.evidence_refs`, and `Observation.evidence_refs`.
- **`ExactSubject`** — the shared exact-commit-subject model
  (`repository_id`, `subject_kind`, `subject_sha`, optional `base_sha`/
  `head_sha`/`synthetic_merge_sha`), used by both
  `CertificationManifest.subject` and `EvidenceArtifact.subject`. Enforces:
  a `pr_head` subject requires `head_sha == subject_sha`; a
  `synthetic_merge` subject requires all three of `base_sha`, `head_sha`,
  and `synthetic_merge_sha`, with `subject_sha == synthetic_merge_sha`. The
  *presence-and-non-null* half of each gate (`pr_head` → `head_sha` present
  and not `null`; `synthetic_merge` → all three present and not `null`) is
  also surfaced in the generated JSON Schema as a model-owned
  `allOf`/`if`/`then` block — the `then` branch pairs `required` with an
  explicit `"not": {"type": "null"}` on each gated property, since
  `required` alone only checks key presence and canonical serialization
  always includes optional fields as `null` rather than omitting them; the
  *equality* half (`head_sha == subject_sha`, etc.) is runtime-only — see
  [Runtime-only invariants](#runtime-only-invariants).
- **`VerificationEnvironment`** — the trusted runner/OS/architecture/
  toolchain/container-digest record for a certification run.
- **`ObservationSource`** — the live-source identity an `Observation` was
  drawn from (`source_type`, `source_id`, optional `source_event_id`).
- **`ExecutorClaim`** — `statement`, `epistemic_status` (default
  `AGENT_REPORTED`), `evidence_refs`: the typed claim model for material
  executor statements. Construction never automatically promotes a claim
  to `VERIFIED` or any stronger status.

## Packet

The authoritative, human-approved work authorization (architecture
section 11.1). Extends `ArtifactEnvelope` with `artifact_type: Literal["packet"]`.

| Field | Type | Notes |
|---|---|---|
| `authorization` | `PacketAuthorization` | `authorized_by`, `authorized_at`, optional `expires_at` (must be later than `authorized_at`) |
| `repository` | `RepositoryTarget` | `repository_id`, `provider="github"`, `owner`, `name`, optional positive `pull_request` |
| `work_start` | `WorkStartAuthorization` | `expected_sha`, `mismatch_policy` |
| `intent` | `PacketIntent` | `problem_statement`, `desired_outcome` |
| `scope` | `PacketScope` | `allowed_paths`, `prohibited_paths`, `allowed_operations`, `prohibited_operations` |
| `requirements` | `tuple[Requirement, ...]` | unique `requirement_id` values |
| `dependency_pins` | `tuple[DependencyPin, ...]` | `repository_id`, `sha`, `cleanliness_required` |
| `verification` | `VerificationRequirements` | `mandatory_lanes`/`advisory_lanes` (each unique, mutually exclusive), `exact_subject_policy`, `synthetic_merge_required` |
| `review` | `PacketReview` | `independent_review_required`, `minimum_severity_blocking` |
| `stop_conditions`, `deliverables`, `completion_report_requirements` | `tuple[ConstrainedText, ...]` | |
| `supersedes` | `Optional[ArtifactReference]` | must not reference the packet's own `artifact_id` |

Packet immutability in this slice is **structural only** (frozen model,
content-digest sealing). Binding packet authorization to a trusted human
identity is deferred to a later validation slice.

## CompletionReport

The execution agent's completion claim (architecture section 11.2).
`artifact_type: Literal["completion_report"]`.

| Field | Type | Notes |
|---|---|---|
| `packet_id`, `run_id` | `GlobalId` | |
| `work_start` | `WorkStartObservation` | `expected_sha`, `actual_sha`, `match` (must equal `expected_sha == actual_sha`), optional `reconciliation` (required iff `match` is `False`, forbidden iff `match` is `True`) |
| `repository_state` | `RepositoryState` | `repository_id`, `base_sha`, `implementation_sha`, optional `pr_head_sha_observed`, `branch` |
| `changes` | `Changes` | `commits` (unique), `files_changed` (unique), `dependency_pins_resolved` |
| `verification_claims` | `VerificationClaims` | `commands_run`, `local_results: tuple[ExecutorClaim, ...]` |
| `deviations`, `known_limitations`, `open_issues` | `tuple[ExecutorClaim, ...]` | material executor statements, default `AGENT_REPORTED` |
| `executor_recommendation` | `ExecutorRecommendation` | |

`Reconciliation.intervening_commits` enumerates each intervening commit as
a `ReconciliationCommit` (`sha`, `disposition`, `rationale`) when the
observed work-start SHA does not match the packet's expected SHA
(architecture 13, INV-002). It MUST be non-empty (`minItems: 1`,
model-owned via `Field`) — an empty reconciliation would satisfy the
presence gate on `WorkStartObservation` without enumerating any commit,
defeating INV-002 accountability. Duplicate `sha` values across entries
are rejected at runtime; `uniqueItems: true` is emitted as a best-effort
schema signal (it rejects fully-identical entries, but JSON Schema has no
"unique by field" primitive to catch same-`sha`/different-disposition
duplicates on its own).

All statements in this artifact default to epistemic status
`AGENT_REPORTED` — a completion report is evidence of what the agent
claims, not proof that the claim is true (architecture section 5.3).

## CertificationManifest

Trusted verification results bound to an exact subject (architecture
section 11.3), produced by trusted CI or a trusted local verifier — never
by the execution agent. `artifact_type: Literal["certification_manifest"]`.

| Field | Type | Notes |
|---|---|---|
| `packet_id`, `run_id` | `GlobalId` | |
| `subject` | `ExactSubject` | shared exact-subject model |
| `environment` | `VerificationEnvironment` | |
| `lanes` | `tuple[LaneResult, ...]` | unique `lane_id`; `completed_at` must not precede `started_at` |
| `evidence` | `tuple[EvidenceReference, ...]` | |
| `result` | `CertificationResult` | `pass` is invalid when any *mandatory* lane did not pass — also surfaced in the generated schema as a model-owned `allOf`/`if`/`then` over `lanes[].conclusion` |

The manifest reuses the inherited `ArtifactEnvelope.policy` field as its
certification policy reference — there is no second, potentially
conflicting top-level policy field.

This model does **not** prove that every packet-required lane is present;
cross-artifact reconciliation between a packet's declared mandatory lanes
and a manifest's actual lanes is deferred to a later validation slice.

## EvidenceArtifact

Metadata and binding for one piece of external verification evidence
(architecture section 8.9). `artifact_type: Literal["evidence_artifact"]`.

| Field | Type | Notes |
|---|---|---|
| `verification_run_id` | `GlobalId` | |
| `subject` | `ExactSubject` | shared exact-subject model |
| `media_type` | `MediaType` | |
| `digest` | `Sha256Digest` | digest of the **external evidence payload** — distinct from the inherited `provenance.content_digest`, which seals this artifact's own envelope content |
| `location` | `GlobalId` | trusted URI/provider location |
| `availability` | `EvidenceAvailability` | |
| `size_bytes` | `Optional[NonNegativeInt]` | |
| `description` | `ConstrainedText` | |

This model records evidence metadata and binding only — it does **not**
fetch, retrieve, or independently verify the referenced remote evidence.

## Observation

A timestamped statement derived from a named source (architecture section
8.14). `artifact_type: Literal["observation"]`.

| Field | Type | Notes |
|---|---|---|
| `subject_id` | `GlobalId` | |
| `source` | `ObservationSource` | `source_type`, `source_id`, optional `source_event_id` |
| `observed_at` | `Timestamp` | |
| `statement` | `ConstrainedText` | |
| `epistemic_status` | `EpistemicStatus` | required, no default |
| `evidence_refs` | `tuple[EvidenceReference, ...]` | |
| `freshness_seconds` | `Optional[PositiveInt]` | |
| `expires_at` | `Optional[Timestamp]` | must be later than `observed_at` |

An observation is a **timestamped record**, not a declaration of current
truth (architecture section 5.4). This model does not compute `STALE`
status or query the source.

## Digest sealing across concrete artifacts (A2A-09)

`seal_artifact` now preserves the exact concrete runtime class:

```python
sealed_packet: Packet = seal_artifact(packet)
assert type(sealed_packet) is Packet
```

Internally, `seal_artifact` reconstructs via `type(envelope).model_validate(data)`
rather than a hard-coded `ArtifactEnvelope.model_validate(data)`, so every
concrete body field is preserved and re-validated. `compute_content_digest`
and `verify_content_digest` already operated polymorphically (they read
`envelope.model_dump(...)` off the actual runtime instance), so they
required no change to support subclasses.

Every concrete body field participates in the content digest: tampering
with any field of any of the five artifacts — top-level or nested — causes
`verify_content_digest` to raise `DigestMismatchError`.

## Construction and sealing example

```python
from datetime import datetime, timezone
from zadc import (
    CONTRACT_VERSION, SCHEMA_ID,
    PolicyReference, ProducerIdentity, Provenance,
    Packet, PacketAuthorization, RepositoryTarget, WorkStartAuthorization,
    PacketIntent, PacketScope, Requirement, DependencyPin,
    VerificationRequirements, PacketReview,
    seal_artifact, verify_content_digest, canonical_json_text,
)

packet = Packet(
    schema=SCHEMA_ID,
    contract_version=CONTRACT_VERSION,
    artifact_type="packet",
    artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
    created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc),
    producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:eric"),
    project_id="zutfen:project:zadc",
    slice_id="ZADC-001A2A",
    slice_instance_id="ZADC-001A2A1",
    policy=PolicyReference(
        policy_id="zutfen:zadc-policy:standard@0.1.0",
        policy_source_sha="a" * 40,
        policy_digest="sha256:" + "b" * 64,
    ),
    provenance=Provenance(parent_artifact_ids=()),
    authorization=PacketAuthorization(
        authorized_by="zutfen:human:eric",
        authorized_at=datetime(2026, 7, 31, 11, 0, 0, tzinfo=timezone.utc),
    ),
    repository=RepositoryTarget(
        repository_id="github:Zutfen-LLC/zadc", provider="github",
        owner="Zutfen-LLC", name="zadc", pull_request=42,
    ),
    work_start=WorkStartAuthorization(expected_sha="a" * 40, mismatch_policy="abort"),
    intent=PacketIntent(problem_statement="...", desired_outcome="..."),
    scope=PacketScope(
        allowed_paths=["src/zadc/**"], prohibited_paths=[],
        allowed_operations=["edit"], prohibited_operations=[],
    ),
    requirements=[
        Requirement(requirement_id="REQ-1", statement="...", acceptance_criteria=["..."])
    ],
    dependency_pins=[],
    verification=VerificationRequirements(
        mandatory_lanes=["lint", "test"], advisory_lanes=[],
        exact_subject_policy="final_pr_head", synthetic_merge_required=False,
    ),
    review=PacketReview(independent_review_required=True, minimum_severity_blocking="blocker"),
    stop_conditions=[], deliverables=[], completion_report_requirements=[],
    supersedes=None,
)

sealed = seal_artifact(packet)  # returns a Packet, not a bare ArtifactEnvelope
verify_content_digest(sealed)
text = canonical_json_text(sealed)
```

## Schema export

`scripts/export_schemas.py` is now data-driven over a fixed list of
(model, output filename, `$id`, title, description) specs, producing:

```text
schemas/0.1/artifact-envelope.schema.json
schemas/0.1/packet.schema.json
schemas/0.1/completion-report.schema.json
schemas/0.1/certification-manifest.schema.json
schemas/0.1/evidence-artifact.schema.json
schemas/0.1/observation.schema.json
```

`export_schema()` (single artifact-envelope export) is retained for
backward compatibility; `export_all_schemas()` exports every schema.
Every artifact instance's inherited `schema` field stays fixed to
`SCHEMA_ID`; each concrete schema's own `$id` matches its filename
(e.g. `packet.schema.json` → `.../0.1/packet.schema.json`). Every business
constraint that appears in a generated schema (`const`, `required`, `enum`,
patterns, and the schema-expressible cross-field conditionals below)
originates from the models — the exporter adds only stable document
metadata and deterministic key ordering. Not every runtime invariant is
schema-expressible; see [Runtime-only invariants](#runtime-only-invariants).

## Runtime-only invariants

Some invariants this slice enforces at construction time have no standard
JSON Schema (Draft 2020-12) vocabulary and are **not** — and cannot be —
surfaced in the generated schemas. An external validator using only the
committed schema will not catch these; only the Python models do.

**Comparisons between two arbitrary sibling values** (JSON Schema has no
way to compare one property's value against another's):

- `PacketAuthorization.expires_at` must be later than `authorized_at`.
- `Observation.expires_at` must be later than `observed_at`.
- `LaneResult.completed_at` must not precede `started_at`.
- `WorkStartObservation.match` must equal `expected_sha == actual_sha`.
- `ExactSubject`: `head_sha == subject_sha` (`pr_head`) and
  `synthetic_merge_sha == subject_sha` (`synthetic_merge`) — only the
  *presence* of the required sibling fields is schema-expressible (see
  above), not their equality to `subject_sha`.
- `Packet.supersedes.artifact_id` must not equal the packet's own
  `artifact_id`.

**Cross-item uniqueness by field** (JSON Schema's `uniqueItems` compares
whole array items, not a single field within each item):

- `Packet.requirements[].requirement_id` must be unique across the packet.
- `VerificationRequirements.mandatory_lanes` / `.advisory_lanes` must each
  be duplicate-free and mutually disjoint.
- `Changes.commits` and `Changes.files_changed` must each be duplicate-free.
- `CertificationManifest.lanes[].lane_id` must be unique across the
  manifest.
- `Reconciliation.intervening_commits[].sha` must be unique; `minItems: 1`
  is schema-expressible (see above), but sha-only deduplication is not.

**Conditional presence** (expressible in principle, not implemented in
this slice — the `match`/`reconciliation` relationship is not schema-gated
because canonical JSON always includes every field, even when `null`,
which makes a bare `required` gate ineffective against the actual `None`
case; the underlying `match` boolean is itself derived from a
runtime-only SHA comparison anyway):

- `WorkStartObservation.reconciliation` must be present when `match` is
  `False` and absent when `match` is `True`.

All of the above are enforced by each model's `model_validator` and are
covered by direct unit tests (constructing the model and asserting
`ValidationError`), independent of schema validation.

## Trust limitations

This slice does **not** implement:

- `ReviewReport`, `DecisionRecord`, `WorkflowBundle`, or a global
  discriminated artifact union across all artifact types;
- derived lifecycle state or cross-artifact referential-integrity
  validation (e.g. matching a `CompletionReport.packet_id` against a
  sealed `Packet`'s digest);
- trusted-human authorization binding, policy evaluation, or
  packet-versus-manifest mandatory-lane reconciliation;
- Git ancestry/diff inspection, GitHub/CI API adapters, freshness
  computation, or remote evidence retrieval;
- CLI validation commands or consumer-specific renderers (Hermes, Codex,
  Claude, CI, human);
- Engram/Flowstate integration or cryptographic signing.

These remain scoped to later slices (A2B and beyond) per
[docs/roadmap.md](roadmap.md).
