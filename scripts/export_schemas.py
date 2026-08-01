#!/usr/bin/env python3
"""Export ZADC JSON Schemas deterministically, one file per artifact model.

Generates Draft 2020-12 JSON Schemas from each model's
``model_json_schema()`` output with deterministic post-processing for
stable output. Output files use sorted pretty JSON with a final newline.

FIX1-E: Schemas are derived from the Pydantic models, not hand-written.

FIX2-A: ``schema`` and ``contract_version`` emit ``const`` entries from
Literal types. They are ``required`` with no defaults.

FIX3-C: ALL business constraints are model-owned. The exporter does NOT
inject or modify any business constraint (patterns, required, const,
allOf, if/then, not, format, enum, additionalProperties). Exporter
post-processing is limited to:
- Stable document metadata ($schema, $id, title, description)
- Deterministic key ordering for presentation

A2A-10: The exporter is data-driven over a fixed list of (model, output
filename, $id, title, description) specs covering the common envelope and
every A2A/A2B1 artifact model. ``export_schema()`` is retained with its
original signature and behavior (single artifact-envelope export) for
backward compatibility with existing callers.

A2B1: The same data-driven spec list gained two more entries — ReviewReport
and DecisionRecord — with no change to the exporter's mutation surface
(still limited to document metadata and deterministic key ordering).

A2B2: The spec list gained a ninth entry — WorkflowBundle — plus a tenth
entry for the global ``ZadcArtifact`` discriminated union, whose schema
source is a Pydantic ``TypeAdapter`` rather than a ``BaseModel`` subclass.
``_SchemaSpec.model`` is generalized to accept either, and
``_raw_json_schema()`` dispatches to the appropriate Pydantic schema-
generation method (``BaseModel.model_json_schema()`` or
``TypeAdapter.json_schema()``); the exporter's mutation surface is
otherwise unchanged.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Add src to path for direct script execution
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from pydantic import BaseModel, TypeAdapter  # noqa: E402

from zadc.models.artifact_union import ZADC_ARTIFACT_ADAPTER  # noqa: E402
from zadc.models.certification_manifest import CertificationManifest  # noqa: E402
from zadc.models.common import ArtifactEnvelope  # noqa: E402
from zadc.models.completion_report import CompletionReport  # noqa: E402
from zadc.models.decision_record import DecisionRecord  # noqa: E402
from zadc.models.evidence_artifact import EvidenceArtifact  # noqa: E402
from zadc.models.observation import Observation  # noqa: E402
from zadc.models.packet import Packet  # noqa: E402
from zadc.models.review_report import ReviewReport  # noqa: E402
from zadc.models.workflow_bundle import WorkflowBundle  # noqa: E402
from zadc.types import SCHEMA_ID  # noqa: E402

#: Base URL for the per-model $id of every A2A concrete-artifact schema.
#: The artifact-envelope schema keeps its historical $id (SCHEMA_ID) rather
#: than adopting this base, to remain byte-identical with the committed A1
#: schema file.
_SCHEMA_BASE_URL = "https://schemas.zutfen.com/zadc/0.1"

# Key-order map for deterministic top-level ordering.
# We place these before the Pydantic-generated keys.
_TOP_LEVEL_KEY_ORDER = [
    "$schema",
    "$id",
    "title",
    "description",
    "type",
    "additionalProperties",
    "required",
    "properties",
]


@dataclass(frozen=True)
class _SchemaSpec:
    """One (schema source, output file, document metadata) schema export target.

    ``model`` is either a concrete ``BaseModel`` subclass (every A1/A2A/A2B1/
    WorkflowBundle entry) or a Pydantic ``TypeAdapter`` (the global
    ``ZadcArtifact`` discriminated-union entry) — see :func:`_raw_json_schema`.
    """

    model: type[BaseModel] | TypeAdapter[Any]
    filename: str
    schema_id: str
    title: str
    description: str


_SCHEMA_SPECS: tuple[_SchemaSpec, ...] = (
    _SchemaSpec(
        model=ArtifactEnvelope,
        filename="artifact-envelope.schema.json",
        schema_id=SCHEMA_ID,
        title="ZADC Artifact Envelope",
        description=(
            "Common artifact envelope for the Zutfen Agentic Development "
            "Contract v0.1. Every ZADC artifact MUST include this envelope."
        ),
    ),
    _SchemaSpec(
        model=Packet,
        filename="packet.schema.json",
        schema_id=f"{_SCHEMA_BASE_URL}/packet.schema.json",
        title="ZADC Packet",
        description=(
            "The authoritative, human-approved work authorization artifact "
            "for the Zutfen Agentic Development Contract v0.1 (architecture "
            "section 11.1). Packet immutability in this slice is structural "
            "only; trusted-human authorization binding is deferred."
        ),
    ),
    _SchemaSpec(
        model=CompletionReport,
        filename="completion-report.schema.json",
        schema_id=f"{_SCHEMA_BASE_URL}/completion-report.schema.json",
        title="ZADC Completion Report",
        description=(
            "The execution agent's completion claim artifact for the "
            "Zutfen Agentic Development Contract v0.1 (architecture "
            "section 11.2). Records claims and local observations; it does "
            "not confer verified status."
        ),
    ),
    _SchemaSpec(
        model=CertificationManifest,
        filename="certification-manifest.schema.json",
        schema_id=f"{_SCHEMA_BASE_URL}/certification-manifest.schema.json",
        title="ZADC Certification Manifest",
        description=(
            "Trusted verification results bound to an exact commit subject "
            "for the Zutfen Agentic Development Contract v0.1 (architecture "
            "section 11.3). Produced by trusted CI or a trusted local "
            "verifier, never by the execution agent."
        ),
    ),
    _SchemaSpec(
        model=EvidenceArtifact,
        filename="evidence-artifact.schema.json",
        schema_id=f"{_SCHEMA_BASE_URL}/evidence-artifact.schema.json",
        title="ZADC Evidence Artifact",
        description=(
            "Metadata and binding for one piece of external verification "
            "evidence for the Zutfen Agentic Development Contract v0.1 "
            "(architecture section 8.9). Records evidence metadata and "
            "binding only; does not fetch or verify remote evidence."
        ),
    ),
    _SchemaSpec(
        model=Observation,
        filename="observation.schema.json",
        schema_id=f"{_SCHEMA_BASE_URL}/observation.schema.json",
        title="ZADC Observation",
        description=(
            "A timestamped statement derived from a named source for the "
            "Zutfen Agentic Development Contract v0.1 (architecture "
            "section 8.14). A timestamped record, not a declaration of "
            "current truth."
        ),
    ),
    _SchemaSpec(
        model=ReviewReport,
        filename="review-report.schema.json",
        schema_id=f"{_SCHEMA_BASE_URL}/review-report.schema.json",
        title="ZADC Review Report",
        description=(
            "A reviewer's structured judgment of an exact subject for the "
            "Zutfen Agentic Development Contract v0.1 (architecture "
            "section A2B1). Records reviewer judgment; it does not "
            "authenticate reviewer identity, prove independence, or "
            "confer merge authorization."
        ),
    ),
    _SchemaSpec(
        model=DecisionRecord,
        filename="decision-record.schema.json",
        schema_id=f"{_SCHEMA_BASE_URL}/decision-record.schema.json",
        title="ZADC Decision Record",
        description=(
            "An authenticated human decision claim for the Zutfen "
            "Agentic Development Contract v0.1 (architecture section "
            "A2B1). A structurally valid record does not, by itself, "
            "authenticate its human identity or confer merge "
            "authorization."
        ),
    ),
    _SchemaSpec(
        model=WorkflowBundle,
        filename="workflow-bundle.schema.json",
        schema_id=f"{_SCHEMA_BASE_URL}/workflow-bundle.schema.json",
        title="ZADC Workflow Bundle",
        description=(
            "The canonical aggregate for one slice instance for the Zutfen "
            "Agentic Development Contract v0.1 (architecture sections 8.15, "
            "11.6). Links referenced artifacts by stable ID and content "
            "digest and carries a recorded derived-state snapshot; it does "
            "not embed full artifacts, recompute derived state, or verify "
            "that a referenced artifact_id resolves to a sealed artifact "
            "of its collection's claimed type."
        ),
    ),
    _SchemaSpec(
        model=ZADC_ARTIFACT_ADAPTER,
        filename="zadc-artifact.schema.json",
        schema_id=f"{_SCHEMA_BASE_URL}/zadc-artifact.schema.json",
        title="ZADC Artifact",
        description=(
            "The global, artifact_type-discriminated union of every "
            "concrete ZADC v0.1 artifact (Packet, CompletionReport, "
            "CertificationManifest, EvidenceArtifact, Observation, "
            "ReviewReport, DecisionRecord, WorkflowBundle) for the Zutfen "
            "Agentic Development Contract v0.1 (architecture section A2B2). "
            "Dispatches each payload to its exact concrete artifact schema "
            "by its artifact_type discriminator."
        ),
    ),
)

#: The artifact-envelope spec, kept addressable for ``_build_envelope_schema``.
_ENVELOPE_SPEC = _SCHEMA_SPECS[0]


def _reorder_dict(data: dict[str, object], key_order: list[str]) -> dict[str, object]:
    """Reorder dict keys with the given order first, then alphabetical."""
    result: dict[str, object] = {}
    for key in key_order:
        if key in data:
            result[key] = data[key]
    for key in sorted(k for k in data if k not in key_order):
        result[key] = data[key]
    return result


def _raw_json_schema(spec: _SchemaSpec) -> dict[str, object]:
    """Return the unprocessed Pydantic-generated JSON Schema for one spec's source.

    Dispatches on the spec's schema source: a ``BaseModel`` subclass uses
    ``model_json_schema()``; a ``TypeAdapter`` (the global ``ZadcArtifact``
    union) uses ``json_schema()``. Both are called with ``mode="validation"``
    for parity. This is the only generalization the exporter needed to
    support a discriminated-union schema source alongside single-model
    sources — no other exporter behavior changed.
    """
    source = spec.model
    if isinstance(source, TypeAdapter):
        return dict(source.json_schema(mode="validation"))
    return dict(source.model_json_schema(mode="validation"))


def _build_schema_for_spec(spec: _SchemaSpec) -> dict[str, object]:
    """Build the JSON Schema for one spec's model with deterministic post-processing.

    FIX3-C: Every business constraint that appears in the output — const
    values, required fields, enums, patterns, UUID conditionals, timestamp
    ranges, -00:00 exclusion, and the subset of cross-field invariants that
    standard JSON Schema can express (e.g. subject-kind-gated required
    fields via ``allOf``/``if``/``then``) — originates from the model's
    Pydantic JSON Schema metadata and custom ``__get_pydantic_json_schema__``
    or ``json_schema_extra`` hooks. The exporter does NOT inject or modify
    any business constraint; it adds only stable document metadata and
    deterministic key ordering.

    Not every runtime cross-field invariant is representable this way.
    Comparisons between two arbitrary sibling values (two SHA strings, two
    timestamps) and cross-item uniqueness-by-field (e.g. unique
    ``requirement_id`` or ``lane_id`` across a list) have no standard JSON
    Schema vocabulary and remain runtime-only, enforced by each model's
    ``model_validator``. See docs/api-a2a-execution-evidence-artifacts.md
    for the itemized list of which invariants are schema-expressible and
    which are runtime-only.
    """
    raw = _raw_json_schema(spec)

    schema: dict[str, object] = dict(raw)
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = spec.schema_id
    schema["title"] = spec.title
    schema["description"] = spec.description

    return _reorder_dict(schema, _TOP_LEVEL_KEY_ORDER)


def _build_envelope_schema() -> dict[str, object]:
    """Build the JSON Schema for ArtifactEnvelope from the model.

    Retained under its original name for backward compatibility with
    existing test callers. Delegates to :func:`_build_schema_for_spec`.
    """
    return _build_schema_for_spec(_ENVELOPE_SPEC)


def _serialize_schema_pretty(schema: dict[str, object]) -> str:
    """Serialize schema as sorted pretty JSON with final newline."""
    text = json.dumps(
        schema,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    return text + "\n"


def _write_schema(spec: _SchemaSpec, target_dir: Path) -> Path:
    """Build and write one schema spec's output file."""
    schema = _build_schema_for_spec(spec)
    text = _serialize_schema_pretty(schema)
    target = target_dir / spec.filename
    target.write_text(text, encoding="utf-8")
    return target


def export_schema(output_dir: Path | None = None) -> Path:
    """Export the artifact-envelope schema to disk.

    Retained with its original signature and behavior for backward
    compatibility with existing callers. Use :func:`export_all_schemas`
    to export every A2A schema.

    Args:
        output_dir: Base output directory. Defaults to ``schemas/`` relative
            to the repository root.

    Returns:
        The path to the written schema file.
    """
    if output_dir is None:
        output_dir = _REPO_ROOT / "schemas"

    target_dir = output_dir / "0.1"
    target_dir.mkdir(parents=True, exist_ok=True)

    return _write_schema(_ENVELOPE_SPEC, target_dir)


def export_all_schemas(output_dir: Path | None = None) -> list[Path]:
    """Export the artifact-envelope schema and every A2A artifact schema.

    Args:
        output_dir: Base output directory. Defaults to ``schemas/`` relative
            to the repository root.

    Returns:
        The paths to every written schema file, in spec-declaration order.
    """
    if output_dir is None:
        output_dir = _REPO_ROOT / "schemas"

    target_dir = output_dir / "0.1"
    target_dir.mkdir(parents=True, exist_ok=True)

    return [_write_schema(spec, target_dir) for spec in _SCHEMA_SPECS]


def main() -> int:
    """CLI entry point for schema export."""
    parser = argparse.ArgumentParser(description="Export ZADC JSON Schemas deterministically.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Base output directory (default: schemas/ relative to repo root).",
    )
    args = parser.parse_args()

    targets = export_all_schemas(args.output_dir)
    for target in targets:
        print(f"Schema exported to: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
