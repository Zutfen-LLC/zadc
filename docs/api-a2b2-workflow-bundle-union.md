# ZADC Public API — A2B2 Workflow Bundle and Global Artifact Union

This document describes the public API surface added by A2B2 on top of the
A1 common artifact foundation (see [docs/api-a1-foundation.md](api-a1-foundation.md)),
the A2A execution/evidence artifacts (see
[docs/api-a2a-execution-evidence-artifacts.md](api-a2a-execution-evidence-artifacts.md)),
and the A2B1 review/decision artifacts (see
[docs/api-a2b1-review-decision-artifacts.md](api-a2b1-review-decision-artifacts.md)).

## Overview

A2B2 completes the canonical v0.1 artifact vocabulary with two additions:

- **`WorkflowBundle`** — a structural artifact that links the authorized
  packet, agent runs, and every downstream artifact produced for one slice
  instance by stable ID and content digest, plus a recorded
  `derived_state` snapshot (architecture sections 8.15, 11.6).
- **`ZadcArtifact`** — a global, `artifact_type`-discriminated Pydantic
  union covering all eight concrete ZADC v0.1 artifacts (`Packet`,
  `CompletionReport`, `CertificationManifest`, `EvidenceArtifact`,
  `Observation`, `ReviewReport`, `DecisionRecord`, `WorkflowBundle`), plus a
  public validation adapter (`validate_artifact`, `validate_artifact_json`).

This slice implements **bundle-internal structural consistency only**. It
does **not** implement lifecycle-state vocabulary or transition rules,
derived-state recomputation, policy evaluation, finding-closure or
blocking-threshold evaluation, trusted reviewer/human identity binding,
merge-authorization derivation, cross-artifact retrieval, external digest
verification of referenced artifacts, or verification that a typed
reference collection's members actually resolve to a sealed artifact of the
claimed type. See [Trust limitations](#trust-limitations).

## WorkflowBundle

The canonical aggregate for one slice instance. Extends `ArtifactEnvelope`
with `artifact_type: Literal["workflow_bundle"]`.

| Field | Type | Notes |
|---|---|---|
| `bundle_id` | `GlobalId` | must equal the envelope `artifact_id` |
| `packet_ref` | `ArtifactReference` | required, singular |
| `agent_run_refs` | `tuple[AgentRunReference, ...]` | unique `run_id` values |
| `completion_report_refs` | `tuple[ArtifactReference, ...]` | `uniqueItems: true` (whole-object, schema-enforced); artifact_id mutually exclusive with every other top-level typed collection (runtime-only) |
| `certification_manifest_refs` | `tuple[ArtifactReference, ...]` | as above |
| `evidence_artifact_refs` | `tuple[ArtifactReference, ...]` | as above |
| `review_report_refs` | `tuple[ArtifactReference, ...]` | as above |
| `decision_record_refs` | `tuple[ArtifactReference, ...]` | as above |
| `observation_refs` | `tuple[ArtifactReference, ...]` | as above |
| `supersedes_bundle_ref` | `Optional[ArtifactReference]` | when present, must not self-reference and its `artifact_id` must appear in `provenance.parent_artifact_ids` |
| `derived_state` | `DerivedStateSnapshot` | see below; `policy` must equal the envelope `policy` |

A bundle never embeds full artifacts in this slice — every reference is by
`artifact_id` + `content_digest` only. The names of the typed reference
collections (e.g. `review_report_refs`) do **not** prove that a referenced
`artifact_id` actually resolves to a sealed artifact of that type; that
referential-integrity check is deferred to a later validation slice.

### Supporting models

- **`AgentRunReference`** — `run_id` (`GlobalId`), `executor_actor_id`
  (`GlobalId`), optional `framework`/`model`/`provider` (`ConstrainedText`).
  Records identity claims only — it is not a top-level artifact and carries
  no content digest. This model does not authenticate the run, the actor,
  the framework, the model, or the provider. `WorkflowBundle.agent_run_refs`
  must have unique `run_id` values.
- **`BundleBlocker`** — `blocker_id` (`StableId`), `code` (`StableId`),
  `statement` (`ConstrainedText`), `artifact_refs`
  (`tuple[ArtifactReference, ...]`, duplicate-free by `artifact_id`,
  `uniqueItems: true` schema-enforced). A blocker is structural
  derived-state output — it is **not** a
  [`Finding`](api-a2b1-review-decision-artifacts.md) and not a new
  authority-bearing artifact. This model does not implement blocker
  severity, finding closure, or policy thresholds.
- **`DerivedStateSnapshot`** — `state` (`StableId`, an opaque identifier —
  not a lifecycle enum defined by this slice), `computed_at` (`Timestamp`),
  `validator_actor_id`/`validator_run_id` (`GlobalId`, claims recorded by
  the bundle; no trust binding is performed), `policy` (`PolicyReference`,
  must equal the enclosing bundle's envelope `policy`),
  `input_artifact_refs` (`tuple[ArtifactReference, ...]`, duplicate-free by
  `artifact_id`), `blockers` (`tuple[BundleBlocker, ...]`, unique
  `blocker_id` values), `stale_artifact_refs` (`tuple[ArtifactReference,
  ...]`, duplicate-free by `artifact_id`), `next_admissible_actions`
  (`tuple[StableId, ...]`, unique values, `uniqueItems: true`
  schema-enforced). **`DerivedStateSnapshot` is recorded validator output —
  it is a claim carried by the bundle. This model does not prove that its
  `state`, `blockers`, `stale_artifact_refs`, or `next_admissible_actions`
  are correct, and does not recompute them from the referenced artifacts.**

## Bundle-internal consistency (runtime-enforced)

`WorkflowBundle` enforces the following at construction (runtime-only
except where noted — see [Schema-expressible vs. runtime-only
invariants](#schema-expressible-vs-runtime-only-invariants)):

1. `bundle_id` must equal the envelope `artifact_id`.
2. No referenced `artifact_id` — in `packet_ref`, any of the six typed
   reference collections, `supersedes_bundle_ref`,
   `derived_state.input_artifact_refs`, any `derived_state.blockers[].artifact_refs`,
   or `derived_state.stale_artifact_refs` — may equal the `WorkflowBundle`'s
   own `artifact_id`.
3. The same `artifact_id` must never appear with conflicting
   `content_digest` values anywhere in the bundle.
4. `packet_ref` and the six typed reference collections together form a set
   of **mutually exclusive** top-level typed artifact references: an
   `artifact_id` must not appear more than once among them (this
   subsumes "each collection is duplicate-free by `artifact_id`").
5. `derived_state.policy` must equal the `WorkflowBundle` envelope
   `policy`.
6. Every `derived_state.input_artifact_refs` entry, every
   `derived_state.blockers[].artifact_refs` entry, and every
   `derived_state.stale_artifact_refs` entry must match an `artifact_id`
   **and** `content_digest` present in the bundle's top-level artifact
   references (`packet_ref` plus the six typed collections).
7. `agent_run_refs` must have unique `run_id` values.
8. When `supersedes_bundle_ref` is present: it must not equal this
   bundle's own `artifact_id` (covered by #2), its `artifact_id` must
   appear in `provenance.parent_artifact_ids` (runtime-only), and
   `provenance.parent_artifact_ids` must be non-empty (schema-owned —
   see [Schema-owned: supersession requires parent
   lineage](#schema-owned-supersession-requires-parent-lineage)).
9. `WorkflowBundle.artifact_id` must never appear in
   `provenance.parent_artifact_ids` — a bundle must not be its own
   provenance parent.
10. `derived_state.computed_at` must not be later than the bundle's own
    `created_at`.

## Global artifact union: `ZadcArtifact`

```python
ZadcArtifact = Annotated[
    Union[
        Packet, CompletionReport, CertificationManifest, EvidenceArtifact,
        Observation, ReviewReport, DecisionRecord, WorkflowBundle,
    ],
    Field(discriminator="artifact_type"),
]
```

A Pydantic discriminated union keyed on the shared envelope field
`artifact_type`. Validating a payload dispatches it to the exact concrete
artifact model for its declared `artifact_type` and returns that concrete
instance — never a bare union or base-class instance. An unknown, missing,
or `null` `artifact_type` is rejected by Pydantic's discriminator
machinery. A payload whose `artifact_type` names one variant but whose body
carries fields belonging only to a different variant is rejected by that
variant's own `extra="forbid"` configuration (every concrete artifact model
is strict) — no additional cross-variant check is needed.

`ZadcArtifact` does not weaken any individual artifact's schema or runtime
validator: dispatch happens first, then the dispatched model's full
constructor (including all of its own `model_validator`s) runs exactly as
it would if constructed directly.

### Public validation adapter

```python
ZADC_ARTIFACT_ADAPTER: TypeAdapter[...]

def validate_artifact(value: object) -> ZadcArtifact: ...
def validate_artifact_json(data: str | bytes | bytearray) -> ZadcArtifact: ...
```

- **`validate_artifact(value)`** — validates a Python mapping (e.g. a
  `dict` from `json.loads`) and returns the exact concrete artifact model.
- **`validate_artifact_json(data)`** — validates canonical JSON text or
  bytes directly (equivalent to `validate_artifact(json.loads(data))`, but
  parses and validates in a single Pydantic call).
- **`ZADC_ARTIFACT_ADAPTER`** — the underlying `pydantic.TypeAdapter`
  backing both functions, exposed for adapter-level operations (e.g.
  `ZADC_ARTIFACT_ADAPTER.json_schema()`).

Both functions raise `pydantic.ValidationError` for unknown, missing,
`null`, or mismatched `artifact_type` values, or for any other validation
failure of the dispatched variant. Validation is strict, consistent with
every concrete artifact model's own `strict=True` configuration — no
separate strict flag is layered on top of the adapter call.

## Schema-expressible vs. runtime-only invariants

Unlike `ReviewReport` and `DecisionRecord` (A2B1), which each carry
artifact-level `allOf`/`if`/`then` schema hooks for their conditional
presence gates, **almost all of `WorkflowBundle`'s cross-collection and
cross-object invariants** (self-reference, digest consistency, top-level
collection exclusivity, derived-state-to-top-level membership, policy
equality, provenance self-parentage, derived-state chronology, and exact
supersession-parent *membership*) are comparisons between two arbitrary
sibling or cross-object values, which have no standard JSON Schema
vocabulary. Those are enforced only by
`WorkflowBundle._check_workflow_bundle_invariants`,
`DerivedStateSnapshot._check_derived_state_invariants`, and
`BundleBlocker._check_artifact_refs`.

One necessary portion of the supersession invariant is schema-expressible,
however: a non-null `supersedes_bundle_ref` requires
`provenance.parent_artifact_ids` to be non-empty. `WorkflowBundle`'s schema
therefore carries exactly **one** top-level `allOf`/`if`/`then` gate for
this — see [Schema-owned: supersession requires parent
lineage](#schema-owned-supersession-requires-parent-lineage) below. This
is necessary, not sufficient: it does not (and cannot) prove that
`supersedes_bundle_ref.artifact_id` is itself a member of
`parent_artifact_ids` — only that the tuple is non-empty. The exact
membership check remains runtime-only.

What **is** schema-expressible and schema-owned for `WorkflowBundle`:

- **`DerivedStateSnapshot.next_admissible_actions`** (`tuple[StableId,
  ...]`) declares `uniqueItems: true` — a scalar-string array, exactly what
  JSON Schema's `uniqueItems` supports.
- Every `tuple[ArtifactReference, ...]` field (the six top-level
  collections, `DerivedStateSnapshot.input_artifact_refs`,
  `DerivedStateSnapshot.stale_artifact_refs`, `BundleBlocker.artifact_refs`)
  also declares `uniqueItems: true`, as a **best-effort whole-object**
  duplicate signal. This rejects two fully identical `{artifact_id,
  content_digest}` objects in the same array, but — unlike the runtime
  check — it does **not** detect two objects that share the same
  `artifact_id` with *different* `content_digest` values, and it cannot
  express cross-collection exclusivity at all. Both of those remain
  runtime-only (see below).

#### Schema-owned: supersession requires parent lineage

```json
{
  "allOf": [
    {
      "if": {
        "properties": {"supersedes_bundle_ref": {"not": {"type": "null"}}},
        "required": ["supersedes_bundle_ref"]
      },
      "then": {
        "properties": {
          "provenance": {"properties": {"parent_artifact_ids": {"minItems": 1}}}
        },
        "required": ["provenance"]
      }
    }
  ]
}
```

When `supersedes_bundle_ref` is present and non-null, `provenance
.parent_artifact_ids` must have at least one item. This is proven
independently by a raw Draft 2020-12 validator against a payload built with
a valid supersession and then mutated to carry an empty
`parent_artifact_ids` — see
`TestWorkflowBundleSchemaSupersessionRequiresParentLineage` in
`tests/test_a2b2_schema_export.py`.

### Runtime-only invariants

The following have no standard JSON Schema (Draft 2020-12) vocabulary and
are enforced only by the Python models' `model_validator`s:

**Comparisons between two arbitrary sibling or cross-object values:**

- `WorkflowBundle.bundle_id` must equal the envelope `artifact_id`.
- No reference position (`packet_ref`, any typed collection,
  `supersedes_bundle_ref`, any `derived_state` reference) may equal the
  bundle's own `artifact_id`.
- `WorkflowBundle.artifact_id` must not appear in
  `provenance.parent_artifact_ids` — a bundle must not be its own
  provenance parent, regardless of whether it is also referenced from a
  typed reference collection.
- `derived_state.computed_at` must not be later than the bundle's own
  `created_at` — an immutable artifact cannot carry a derived-state
  snapshot computed after its own declared creation time.
- `derived_state.policy` must equal the envelope `policy`.
- `supersedes_bundle_ref.artifact_id` must appear in
  `provenance.parent_artifact_ids` — a membership check against a sibling
  tuple field's element values (the schema-owned gate above only proves
  the tuple is non-empty, not that this exact value is a member).
- Every `derived_state.input_artifact_refs` / `blockers[].artifact_refs` /
  `stale_artifact_refs` entry's `artifact_id` **and** `content_digest` must
  match an entry in the bundle's top-level artifact references — both a
  membership check and a value-equality check against cross-object data.

**Cross-item uniqueness by a field nested inside array items** (distinct
from the whole-object `uniqueItems` signal above — JSON Schema's
`uniqueItems` compares whole array items, not one field within each item):

- `WorkflowBundle.agent_run_refs[].run_id` must be unique.
- The same `artifact_id` must not appear in more than one of
  `WorkflowBundle`'s top-level typed reference collections (`packet_ref`
  plus the six `*_refs` tuples) — and, within any one collection, must not
  repeat.
- `DerivedStateSnapshot.blockers[].blocker_id` must be unique.
- `BundleBlocker.artifact_refs[].artifact_id` must be duplicate-free
  (per blocker).
- `DerivedStateSnapshot.input_artifact_refs[].artifact_id` and
  `DerivedStateSnapshot.stale_artifact_refs[].artifact_id` must each be
  duplicate-free within their own tuple.

All of the above are covered by direct unit tests (constructing the model
and asserting `ValidationError`) and by tests that mutate the raw sealed
JSON and assert the *schema itself* still accepts it (proving these gates
are not schema-enforced) — see `tests/test_a2b2_workflow_bundle.py` and
`tests/test_a2b2_schema_export.py`.

## Authority boundaries

- `DerivedStateSnapshot` is **recorded validator output**, not a
  recomputed or trusted fact. A structurally valid `WorkflowBundle` does
  not prove that its `derived_state.state`, `blockers`,
  `stale_artifact_refs`, or `next_admissible_actions` are correct — a
  later validation slice (ZADC-001B/C) computes and recomputes derived
  state from the referenced artifacts under a pinned policy.
- The **name** of a typed reference collection (e.g.
  `certification_manifest_refs`) does not prove that the referenced
  `artifact_id` actually resolves to a sealed artifact of that type. This
  slice checks only that `artifact_id`/`content_digest` pairs are
  internally consistent within the bundle — it never fetches or validates
  the referenced artifact's own content.
- `AgentRunReference` and `DerivedStateSnapshot.validator_actor_id`/
  `validator_run_id` are unauthenticated claims recorded by whoever
  assembled the bundle. No trust binding is performed against them.

## Digest sealing, canonicalization, and schema export

`seal_artifact`, `compute_content_digest`, and `verify_content_digest`
operate polymorphically and require no artifact-specific code — they
already preserve the concrete runtime class (`WorkflowBundle`) and cover
every body field, top-level or nested, exactly as for the seven other
concrete artifacts (see
[docs/api-a2a-execution-evidence-artifacts.md#digest-sealing-across-concrete-artifacts-a2a-09](api-a2a-execution-evidence-artifacts.md)).
Every `WorkflowBundle` body field — including nested reference tuples,
`derived_state`, its `blockers`, and `supersedes_bundle_ref` — participates
in content-digest computation; tampering with any of them after sealing is
detected by `verify_content_digest` raising `DigestMismatchError`.

`scripts/export_schemas.py`'s data-driven spec list gained two entries:

```text
schemas/0.1/workflow-bundle.schema.json
schemas/0.1/zadc-artifact.schema.json
```

The exporter's `_SchemaSpec.model` field was generalized to accept either a
`BaseModel` subclass (as before) or a `pydantic.TypeAdapter` (for the
`zadc-artifact.schema.json` union entry), dispatched by a small new
`_raw_json_schema()` helper. No other exporter behavior changed — mutation
remains limited to document metadata (`$schema`, `$id`, `title`,
`description`) and deterministic key ordering. All eight previously
committed schema files (`artifact-envelope`, `packet`, `completion-report`,
`certification-manifest`, `evidence-artifact`, `observation`,
`review-report`, `decision-record`) regenerate byte-identically —
unchanged by this slice.

`zadc-artifact.schema.json` is a Draft 2020-12 schema whose top level is a
`oneOf` of eight `$ref`s into `$defs`, plus a `discriminator` object
(`propertyName: "artifact_type"`, with a `mapping` from each of the eight
`artifact_type` values to its `$defs` entry) — matching the discriminated
union Pydantic itself generates, with only the same document-metadata and
key-ordering post-processing applied to every other exported schema.

## Construction and sealing example

```python
from datetime import datetime, timezone
from zadc import (
    CONTRACT_VERSION, SCHEMA_ID,
    PolicyReference, ProducerIdentity, Provenance, ArtifactReference,
    WorkflowBundle, AgentRunReference, BundleBlocker, DerivedStateSnapshot,
    seal_artifact, verify_content_digest, canonical_json_text,
    validate_artifact, validate_artifact_json,
)

policy = PolicyReference(
    policy_id="zutfen:zadc-policy:standard@0.1.0",
    policy_source_sha="a" * 40,
    policy_digest="sha256:" + "b" * 64,
)

# packet_ref, completion_ref, ... are ArtifactReference(artifact_id=..., content_digest=...)
# pointing at already-sealed artifacts (see the seven other API docs for how
# to construct and seal each one).

derived_state = DerivedStateSnapshot(
    state="awaiting_review",
    computed_at=datetime(2026, 8, 1, 11, 30, 0, tzinfo=timezone.utc),
    validator_actor_id="zutfen:validator:zadc",
    validator_run_id="urn:uuid:00000000-0000-0000-0000-000000000900",
    policy=policy,
    input_artifact_refs=(packet_ref,),
    blockers=(),
    stale_artifact_refs=(),
    next_admissible_actions=("submit_review",),
)

bundle = WorkflowBundle(
    schema=SCHEMA_ID, contract_version=CONTRACT_VERSION,
    artifact_type="workflow_bundle",
    artifact_id="urn:uuid:00000000-0000-0000-0000-000000000301",
    created_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
    producer=ProducerIdentity(actor_type="validator", actor_id="zutfen:validator:zadc"),
    project_id="zutfen:project:zadc",
    slice_id="ZADC-001A2B2", slice_instance_id="ZADC-001A2B21",
    policy=policy,
    provenance=Provenance(parent_artifact_ids=()),
    bundle_id="urn:uuid:00000000-0000-0000-0000-000000000301",
    packet_ref=packet_ref,
    agent_run_refs=(),
    completion_report_refs=(), certification_manifest_refs=(),
    evidence_artifact_refs=(), review_report_refs=(),
    decision_record_refs=(), observation_refs=(),
    supersedes_bundle_ref=None,
    derived_state=derived_state,
)

sealed = seal_artifact(bundle)
verify_content_digest(sealed)

text = canonical_json_text(sealed)
reloaded = validate_artifact_json(text)  # -> WorkflowBundle, dispatched via ZadcArtifact
assert type(reloaded) is WorkflowBundle
```

## Trust limitations

This slice does **not** implement:

- lifecycle-state vocabulary, transition rules, or state recomputation —
  `DerivedStateSnapshot` is recorded validator output only, never
  recomputed or trust-checked by this slice;
- policy evaluation, finding-closure, or blocking-threshold evaluation;
- accepted-risk reconciliation;
- trusted reviewer or human identity binding beyond the A2B1
  internal-consistency checks;
- merge-authorization derivation;
- cross-artifact retrieval or verification that a typed reference
  collection's members actually resolve to a sealed artifact of the
  collection's claimed type — the bundle-internal checks in this slice
  operate entirely on the `artifact_id`/`content_digest` pairs present in
  the bundle payload itself;
- external digest verification of referenced artifacts (fetching and
  re-hashing the artifact a reference points at);
- Git ancestry/diff inspection, live GitHub/CI/deployment/billing/service
  adapters;
- freshness computation or evidence retrieval;
- embedding full artifacts in a bundle, or portable offline bundle
  validation;
- consumer-specific renderers or CLI validation commands;
- Engram/Flowstate integration or cryptographic signing.

These remain scoped to A3 and later slices per [docs/roadmap.md](roadmap.md).
