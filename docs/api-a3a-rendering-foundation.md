# ZADC Public API — A3A Rendering Foundation

This document describes the public API surface added by A3A on top of the
A1 common artifact foundation (see
[docs/api-a1-foundation.md](api-a1-foundation.md)), the A2A execution/evidence
artifacts (see
[docs/api-a2a-execution-evidence-artifacts.md](api-a2a-execution-evidence-artifacts.md)),
the A2B1 review/decision artifacts (see
[docs/api-a2b1-review-decision-artifacts.md](api-a2b1-review-decision-artifacts.md)),
and the A2B2 WorkflowBundle and global artifact union (see
[docs/api-a2b2-workflow-bundle-union.md](api-a2b2-workflow-bundle-union.md)).

## Overview

A3A adds a deterministic, **non-authoritative** rendering layer over the
eight canonical ZADC artifacts (architecture section 8.16, "Rendered view").
A rendered view is a purpose-specific **projection** of one verified sealed
canonical artifact for a given consumer. It is **not** a canonical artifact:
it carries no artifact identity, content digest, producer, authority,
approval, or lifecycle state of its own. Every value in a view is quoted
from the single source artifact it is bound to by exact artifact ID and
content digest.

A3A supplies default renderers for two consumers only:

- **`human`** — `HumanMarkdownRenderer` (Markdown).
- **`ci`** — `CiJsonRenderer` (deterministic canonical JSON).

The `hermes`, `codex`, and `claude` consumers are part of the
`RenderConsumer` vocabulary **now** (so the public enum does not change when
A3B lands their implementations) but have no registered renderer in A3A;
requests for them fail explicitly with `RendererNotFoundError`.

This slice implements presentation only. See
[Non-authoritative boundary](#non-authoritative-boundary).

## Public API

### `RenderConsumer`

```python
RenderConsumer = Literal["human", "ci", "hermes", "codex", "claude"]
```

The complete architecture-level consumer vocabulary. A3A registers renderers
for `human` and `ci` only.

### `RendererReference`

Stable, explicit identity for one renderer implementation.

| Field | Type | Notes |
|---|---|---|
| `renderer_id` | `StableId` | e.g. `zadc-human-markdown` |
| `renderer_version` | `StableId` | e.g. `0.1.0` |

Default identities:

| Consumer | `renderer_id` | `renderer_version` |
|---|---|---|
| `human` | `zadc-human-markdown` | `0.1.0` |
| `ci` | `zadc-ci-json` | `0.1.0` |

### `RenderedView`

A non-authoritative projection record. Strict, frozen, `extra="forbid"`,
`strict=True`.

| Field | Type | Notes |
|---|---|---|
| `schema` | `const` | `https://schemas.zutfen.com/zadc/0.1/rendered-view.schema.json` |
| `view_version` | `const` | `0.1.0` |
| `non_authoritative` | `const` | `true` |
| `consumer` | `RenderConsumer` | the consumer this view was rendered for |
| `media_type` | `MediaType` | the renderer's output media type |
| `renderer` | `RendererReference` | which renderer produced the content |
| `rendered_at` | `Timestamp` | explicit caller input; runtime-only `>= source_created_at` |
| `source_ref` | `ArtifactReference` | the source `artifact_id` + **verified** `content_digest` |
| `source_artifact_type` | `ArtifactType` | copied from the source |
| `source_contract_version` | `const` | `0.1.0` |
| `source_created_at` | `Timestamp` | copied from the source |
| `source_project_id` | `GlobalId` | copied from the source |
| `source_slice_id` | `SliceId` | copied from the source |
| `source_slice_instance_id` | `SliceId` | copied from the source |
| `source_policy` | `PolicyReference` | copied from the source |
| `content` | `str` (`minLength: 1`) | the rendered, non-empty content |

A `RenderedView` is **not** an `ArtifactEnvelope` and is **not** added to
`ArtifactType` or `ZadcArtifact`. A `RenderedView` payload is rejected by
`validate_artifact` and `validate_artifact_json` (it carries no `artifact_type`
discriminator).

The `rendered_at >= source_created_at` chronology invariant is a comparison
between two arbitrary timestamp values, which has no standard JSON Schema
vocabulary. It is enforced at runtime only, at `RenderedView` construction,
and documented in the generated schema description. The schema independently
accepts a chronologically-invalid view with otherwise-valid timestamps.

### `RendererProtocol`

A runtime-checkable, narrowly typed protocol every renderer satisfies:

```python
class RendererProtocol(Protocol):
    consumer: RenderConsumer
    media_type: MediaType
    renderer: RendererReference
    def render_content(self, artifact: ZadcArtifact) -> str: ...
```

Renderer implementations return **content only**. The shared
`render_artifact` wrapper performs source verification and constructs the
`RenderedView`. Renderers receive no mutable global context and must produce
deterministic output for a given verified artifact and renderer version. No
renderer calls the current clock (`rendered_at` is explicit caller input).

### `RendererRegistry`

An immutable registry mapping consumers to renderer instances.

- Constructed from an explicit, finite renderer sequence.
- Rejects **duplicate** consumer registrations at construction (`ValueError`).
- Exposes **no** mutable registration surface afterward.
- Lookup for an unregistered consumer raises `RendererNotFoundError` (this
  includes the reserved-but-unimplemented `hermes`, `codex`, and `claude`
  consumers).
- No entry-point discovery, dynamic imports, plugins, filesystem scanning, or
  network loading.

```python
registry = RendererRegistry((HumanMarkdownRenderer(), CiJsonRenderer()))
registry.get("human")      # -> HumanMarkdownRenderer
registry.get("hermes")     # -> raises RendererNotFoundError
registry.consumers         # -> ("human", "ci")
```

`DEFAULT_RENDERER_REGISTRY` is the registry containing exactly
`HumanMarkdownRenderer` and `CiJsonRenderer`.

### `render_artifact`

```python
def render_artifact(
    artifact: ZadcArtifact,
    *,
    rendered_at: datetime,
    consumer: RenderConsumer,
    registry: Optional[RendererRegistry] = None,
) -> RenderedView
```

The public entrypoint:

1. **Verifies** the source content digest *before* selecting or running any
   renderer. An unsealed source raises `DigestMissingError`; a tampered
   source raises `DigestMismatchError`. Verification precedes renderer
   selection, so a bad source never reaches a renderer.
2. **Selects** the renderer for `consumer` from `registry` (defaulting to
   `DEFAULT_RENDERER_REGISTRY`); an unregistered consumer raises
   `RendererNotFoundError`.
3. **Renders** content via `renderer.render_content(artifact)`.
4. **Constructs** a bound `RenderedView`, copying every `source_*` field
   directly from the verified source. `source_ref` uses the source
   `artifact_id` and the verified `provenance.content_digest`.

The source artifact and its canonical serialization are left byte-identical.

## Renderers

### `HumanMarkdownRenderer` (`consumer="human"`)

Identity: `zadc-human-markdown @ 0.1.0`, media type `text/markdown`. Renders
all eight artifact variants as deterministic Markdown:

- Begins with a prominent **NON-AUTHORITATIVE RENDERED VIEW** notice.
- Displays the verified source identity, producer, provenance, and policy as
  labeled inline-code values.
- Renders the **complete canonical JSON** of the source artifact inside a
  single **dynamically-fenced** code block. The fence length is chosen
  strictly longer than the longest run of backticks anywhere in that JSON, so
  source-controlled prose containing pipes, Markdown headings, HTML, links,
  one-to-five backticks, triple-backtick fences, Unicode, tabs, and newlines
  remains **data**, never surrounding Markdown structure.
- The canonical JSON block guarantees complete, untruncated, unredacted,
  unnormalized, ordering-preserving reproduction of every source body field
  (lists/tuples render as JSON arrays in their original order; keys are
  recursively sorted for hash-order independence).

Type-specific authority caveats appear explicitly:

- **ReviewReport** — `reviewer_recommendation` is labeled a recorded reviewer
  judgment, not an authorization.
- **DecisionRecord** — `decision`/`decided_by` are labeled a recorded decision
  claim whose trusted identity and live-state validity are not established by
  rendering.
- **WorkflowBundle** — `derived_state` is labeled a recorded snapshot that was
  not recomputed by the renderer.

The renderer introduces no `PASS`, `FAIL`, `approved`, `verified`,
`mergeable`, `current`, `fresh`, or `authoritative` conclusions of its own;
any such values are directly quoted source data inside the canonical JSON
block.

### `CiJsonRenderer` (`consumer="ci"`)

Identity: `zadc-ci-json @ 0.1.0`, media type `application/json`. Renders all
eight artifact variants as deterministic ZADC Canonical JSON.

The payload is a strict, frozen, `extra="forbid"` projection record that
includes `non_authoritative=true`, the exact verified `source_ref`,
`artifact_type`, `contract_version`, project/slice identities, `source`
`policy`, `producer`, `provenance`, and the complete canonical source artifact
payload under the single documented key **`source_artifact`**:

```python
import json

view = render_artifact(sealed, rendered_at=at, consumer="ci")
payload = json.loads(view.content)
payload["source_artifact"] == json.loads(canonical_json_text(sealed))  # True
```

The renderer emits no ANSI text, Markdown, environment-specific paths,
wall-clock values, GitHub URLs, or provider-specific status conclusions, and
does not convert recorded derived state or recommendations into CI
success/failure.

## Determinism and semantic preservation

For a fixed artifact, `rendered_at`, renderer identity, and registry, the
canonical JSON of a `RenderedView` is byte-identical across repeated
processes. Renderer output is invariant across list-versus-tuple construction
of semantically identical source artifacts, and field construction order does
not affect output. Rendering a source through the human and CI renderers
produces the same `source_ref`. Rendering never changes the source content
digest.

Rendered content may reorganize presentation but must not add requirements,
permissions, authority, accepted risk, lifecycle transitions, or merge
conclusions.

## Schema

`schemas/0.1/rendered-view.schema.json` is generated by the data-driven
exporter from the `RenderedView` model (Draft 2020-12). All business
constraints (consts, enums, required fields, identifier formats, timestamp
formats, nested strictness) originate from the model. It is validated
independently with `Draft202012Validator` and `FormatChecker`, and is **not**
added to `zadc-artifact.schema.json`. All ten prior schemas regenerate
byte-identically alongside it.

## Non-authoritative boundary

Rendering **does not**:

- authenticate producer, reviewer, or human-decider identities;
- reconcile live repository state;
- verify that referenced artifacts resolve;
- derive or recompute lifecycle state;
- evaluate policy;
- approve or authorize any merge;
- accept or reconcile risk;
- establish freshness.

All authority remains with the canonical source artifact identified by
`source_ref`. These concerns are governed by later slices.

## Examples

### Human

```python
from datetime import UTC, datetime

from zadc import seal_artifact, render_artifact

sealed = seal_artifact(packet)
view = render_artifact(
    sealed,
    rendered_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
    consumer="human",
)
print(view.media_type)   # text/markdown
print(view.content)      # the Markdown projection
```

### CI

```python
view = render_artifact(
    sealed,
    rendered_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
    consumer="ci",
)
print(view.media_type)   # application/json
print(view.content)      # deterministic canonical JSON
```
