#!/usr/bin/env python3
"""Export the ZADC artifact-envelope JSON Schema deterministically.

Generates a Draft 2020-12 JSON Schema from ``ArtifactEnvelope.model_json_schema()``
with deterministic post-processing for stable output. The output file uses
sorted pretty JSON with a final newline.

FIX1-E: The schema is derived from the Pydantic model, not hand-written.
Post-processing only adds $schema, $id, title, description, and reorders keys.

Usage:
    python scripts/export_schemas.py [--output-dir schemas]

The schema is written to ``schemas/0.1/artifact-envelope.schema.json``.
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path for direct script execution
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from zadc.models.common import ArtifactEnvelope  # noqa: E402
from zadc.types import SCHEMA_ID  # noqa: E402

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


def _reorder_dict(data: dict[str, object], key_order: list[str]) -> dict[str, object]:
    """Reorder dict keys with the given order first, then alphabetical."""
    result: dict[str, object] = {}
    for key in key_order:
        if key in data:
            result[key] = data[key]
    for key in sorted(k for k in data if k not in key_order):
        result[key] = data[key]
    return result


def _build_envelope_schema() -> dict[str, object]:
    """Build the JSON Schema for ArtifactEnvelope from the model.

    Uses ``ArtifactEnvelope.model_json_schema(mode='validation')`` to derive
    the schema, then applies deterministic post-processing.
    """
    # Generate schema from the Pydantic model.
    raw = ArtifactEnvelope.model_json_schema(mode="validation")

    # Post-process: add schema metadata, flatten $defs, and reorder.
    schema: dict[str, object] = dict(raw)

    # Add stable metadata.
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = SCHEMA_ID
    schema["title"] = "ZADC Artifact Envelope"
    schema["description"] = (
        "Common artifact envelope for the Zutfen Agentic Development "
        "Contract v0.1. Every ZADC artifact MUST include this envelope."
    )

    # Ensure additionalProperties is false at the top level.
    schema["additionalProperties"] = False

    # Apply deterministic key ordering at the top level.
    schema = _reorder_dict(schema, _TOP_LEVEL_KEY_ORDER)

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
        output_dir = _REPO_ROOT / "schemas"

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
