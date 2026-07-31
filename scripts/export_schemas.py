#!/usr/bin/env python3
"""Export the ZADC artifact-envelope JSON Schema deterministically.

Generates a Draft 2020-12 JSON Schema for the common artifact envelope.
The output file uses sorted pretty JSON with a final newline, making it
reproducible and suitable for byte-level regression comparison.

Usage:
    python scripts/export_schemas.py [--output-dir schemas]

The schema is written to ``schemas/0.1/artifact-envelope.schema.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from zadc.types import CONTRACT_VERSION, SCHEMA_ID


def _build_envelope_schema() -> dict[str, object]:
    """Build the JSON Schema for ArtifactEnvelope (Draft 2020-12)."""
    actor_types = ["human", "agent", "ci", "validator", "service"]
    artifact_types = [
        "packet",
        "completion_report",
        "certification_manifest",
        "review_report",
        "decision_record",
        "workflow_bundle",
        "evidence_artifact",
        "observation",
    ]

    sha256_digest_pattern = r"^sha256:[0-9a-f]{64}$"
    git_sha_pattern = r"^[0-9a-f]{40}$"
    # Stable IDs: non-empty, no control characters, no leading/trailing whitespace.
    stable_id_pattern = r"^[^\s]+(.*[^\s]+)?$"

    # Datetime RFC 3339 pattern with optional fractional seconds and uppercase Z.
    # This pattern matches the canonical serialization output.
    datetime_pattern = (
        r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
        r"[0-9]{2}:[0-9]{2}:[0-9]{2}"
        r"(\.[0-9]+)?"
        r"(Z|[+-][0-9]{2}:[0-9]{2})$"
    )

    schema: dict[str, object] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "ZADC Artifact Envelope",
        "description": (
            "Common artifact envelope for the Zutfen Agentic Development "
            "Contract v0.1. Every ZADC artifact MUST include this envelope."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema",
            "contract_version",
            "artifact_type",
            "artifact_id",
            "created_at",
            "producer",
            "project_id",
            "slice_id",
            "slice_instance_id",
            "policy",
            "provenance",
        ],
        "properties": {
            "schema": {
                "type": "string",
                "const": SCHEMA_ID,
            },
            "contract_version": {
                "type": "string",
                "const": CONTRACT_VERSION,
            },
            "artifact_type": {
                "type": "string",
                "enum": artifact_types,
            },
            "artifact_id": {
                "type": "string",
                "pattern": stable_id_pattern,
                "minLength": 1,
            },
            "created_at": {
                "type": "string",
                "pattern": datetime_pattern,
            },
            "producer": {
                "type": "object",
                "additionalProperties": False,
                "required": ["actor_type", "actor_id"],
                "properties": {
                    "actor_type": {
                        "type": "string",
                        "enum": actor_types,
                    },
                    "actor_id": {
                        "type": "string",
                        "pattern": stable_id_pattern,
                        "minLength": 1,
                    },
                    "run_id": {
                        "type": ["string", "null"],
                        "pattern": stable_id_pattern,
                    },
                    "model": {
                        "type": ["string", "null"],
                    },
                    "provider": {
                        "type": ["string", "null"],
                    },
                },
            },
            "project_id": {
                "type": "string",
                "pattern": stable_id_pattern,
                "minLength": 1,
            },
            "slice_id": {
                "type": "string",
                "pattern": stable_id_pattern,
                "minLength": 1,
            },
            "slice_instance_id": {
                "type": "string",
                "pattern": stable_id_pattern,
                "minLength": 1,
            },
            "policy": {
                "type": "object",
                "additionalProperties": False,
                "required": ["policy_id", "policy_source_sha", "policy_digest"],
                "properties": {
                    "policy_id": {
                        "type": "string",
                        "pattern": stable_id_pattern,
                        "minLength": 1,
                    },
                    "policy_source_sha": {
                        "type": "string",
                        "pattern": git_sha_pattern,
                    },
                    "policy_digest": {
                        "type": "string",
                        "pattern": sha256_digest_pattern,
                    },
                },
            },
            "provenance": {
                "type": "object",
                "additionalProperties": False,
                "required": ["parent_artifact_ids"],
                "properties": {
                    "parent_artifact_ids": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "pattern": stable_id_pattern,
                            "minLength": 1,
                        },
                    },
                    "content_digest": {
                        "type": ["string", "null"],
                        "pattern": sha256_digest_pattern,
                    },
                },
            },
        },
    }

    return schema


def _serialize_schema_pretty(schema: dict[str, object]) -> str:
    """Serialize schema as sorted pretty JSON with final newline."""
    text = json.dumps(
        schema,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    return text + "\n"


def export_schema(output_dir: Path | None = None) -> Path:
    """Export the artifact-envelope schema to disk.

    Args:
        output_dir: Base output directory. Defaults to ``schemas/`` relative
            to the repository root.

    Returns:
        The path to the written schema file.
    """
    if output_dir is None:
        repo_root = Path(__file__).resolve().parent.parent
        output_dir = repo_root / "schemas"

    target_dir = output_dir / "0.1"
    target_dir.mkdir(parents=True, exist_ok=True)

    schema = _build_envelope_schema()
    text = _serialize_schema_pretty(schema)
    target = target_dir / "artifact-envelope.schema.json"
    target.write_text(text, encoding="utf-8")
    return target


def main() -> int:
    """CLI entry point for schema export."""
    parser = argparse.ArgumentParser(
        description="Export ZADC artifact-envelope JSON Schema deterministically."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Base output directory (default: schemas/ relative to repo root).",
    )
    args = parser.parse_args()

    target = export_schema(args.output_dir)
    print(f"Schema exported to: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
