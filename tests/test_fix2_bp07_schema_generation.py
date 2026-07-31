"""FIX2-BP-07: Schema generation remains model-owned and reproducible.

Tests that the schema originates from ArtifactEnvelope.model_json_schema(),
const/required/pattern/timestamp constraints come from model metadata,
post-processing is limited to stable metadata, and regeneration is byte-identical.
"""

import json
import sys
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_schemas import _build_envelope_schema  # noqa: E402

_SCHEMA_PATH = _REPO_ROOT / "schemas" / "0.1" / "artifact-envelope.schema.json"


class TestSchemaReproducibility:
    """Regeneration produces byte-identical committed schema."""

    def test_generated_equals_committed(self) -> None:
        committed = _SCHEMA_PATH.read_bytes()
        generated_schema: dict[str, Any] = cast(dict[str, Any], _build_envelope_schema())
        generated_text = (
            json.dumps(
                generated_schema,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        assert committed == generated_text.encode("utf-8")

    def test_zero_diff_on_regenerate(self) -> None:
        committed = _SCHEMA_PATH.read_text()
        schema: dict[str, Any] = cast(dict[str, Any], _build_envelope_schema())
        generated = (
            json.dumps(
                schema,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        assert committed == generated


class TestSchemaModelOwnedConstraints:
    """Const, required, pattern, enum, timestamp constraints originate from model metadata."""

    def test_const_from_literal_type(self) -> None:
        schema_str = json.dumps(_build_envelope_schema())
        # const values from Literal types
        assert '"const": "https://schemas.zutfen.com/zadc/0.1/artifact.schema.json"' in schema_str
        assert '"const": "0.1.0"' in schema_str

    def test_required_fields_from_non_optional_declarations(self) -> None:
        schema: dict[str, Any] = cast(dict[str, Any], _build_envelope_schema())
        required = schema["required"]
        assert "schema" in required
        assert "contract_version" in required
        assert "provenance" in required

    def test_parent_artifact_ids_required(self) -> None:
        schema: dict[str, Any] = cast(dict[str, Any], _build_envelope_schema())
        prov_def = schema["$defs"]["Provenance"]
        assert "parent_artifact_ids" in prov_def["required"]

    def test_patterns_from_string_constraints(self) -> None:
        schema_str = json.dumps(_build_envelope_schema())
        # Digest pattern
        assert "sha256:[0-9a-f]{64}" in schema_str
        # Git SHA pattern
        assert "[0-9a-f]{40}" in schema_str
        # GlobalId pattern (lowercase scheme)
        assert "[a-z][a-z0-9" in schema_str

    def test_enums_from_literal_types(self) -> None:
        schema_str = json.dumps(_build_envelope_schema())
        assert '"packet"' in schema_str
        assert '"human"' in schema_str

    def test_additional_properties_false(self) -> None:
        schema: dict[str, Any] = cast(dict[str, Any], _build_envelope_schema())
        assert schema["additionalProperties"] is False

    def test_timestamp_pattern_in_schema(self) -> None:
        schema: dict[str, Any] = cast(dict[str, Any], _build_envelope_schema())
        props = schema["properties"]
        assert "pattern" in props["created_at"]

    def test_dollar_defs_prove_model_derivation(self) -> None:
        schema_str = json.dumps(_build_envelope_schema())
        assert "$defs" in schema_str


class TestSchemaPostProcessingLimits:
    """Exporter post-processing is limited to stable metadata, reference/layout
    normalization, and deterministic presentation."""

    def test_no_local_paths(self) -> None:
        schema_str = _SCHEMA_PATH.read_text()
        assert "/home/" not in schema_str
        assert "/tmp/" not in schema_str

    def test_no_timestamps(self) -> None:
        import re

        schema_str = _SCHEMA_PATH.read_text()
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:", schema_str)

    def test_no_random_values(self) -> None:
        schema_str = _SCHEMA_PATH.read_text().lower()
        assert "uuid-" not in schema_str  # no generated UUIDs
        assert "temp" not in schema_str

    def test_check_schema_valid(self) -> None:
        schema = json.loads(_SCHEMA_PATH.read_text())
        Draft202012Validator.check_schema(schema)
