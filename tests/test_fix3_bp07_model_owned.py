"""FIX3-BP-07: Model-owned schema constraints.

Proves that every FIX3 business constraint exists in the raw model-generated
schema BEFORE exporter post-processing, and that the exporter does not
mutate business constraints.
"""

import json
import sys
from pathlib import Path
from typing import Any, cast

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_schemas import _build_envelope_schema  # noqa: E402

from zadc.models.common import ArtifactEnvelope  # noqa: E402

_SCHEMA_PATH = _REPO_ROOT / "schemas" / "0.1" / "artifact-envelope.schema.json"


def _raw_model_schema() -> dict[str, Any]:
    """Generate the raw model schema with zero exporter post-processing."""
    return ArtifactEnvelope.model_json_schema(mode="validation")


class TestRawModelSchemaOwnsConstraints:
    """FIX3-BP-07: Raw model schema already contains all FIX3 constraints."""

    def test_raw_schema_has_global_id_allOf(self) -> None:
        """The percent-aware GlobalId allOf is in the raw model schema."""
        raw = _raw_model_schema()
        props = raw["properties"]
        aid = props["artifact_id"]
        assert "allOf" in aid
        all_of = aid["allOf"]
        # Base pattern
        assert any("pattern" in item for item in all_of if "if" not in item)
        # UUID conditional
        assert any("if" in item and "then" in item for item in all_of)

    def test_raw_schema_has_percent_aware_pattern(self) -> None:
        """The base pattern rejects bare % (uses %(?:...) not just %)."""
        raw = _raw_model_schema()
        props = raw["properties"]
        aid = props["artifact_id"]
        all_of = aid["allOf"]
        base_pattern_item = [i for i in all_of if "pattern" in i and "if" not in i][0]
        pattern = base_pattern_item["pattern"]
        # Must contain % followed by [0-9A-F]{2}, not bare %
        assert "%[0-9A-F]{2}" in pattern
        # Must NOT have bare % in the character class
        assert "=%]" not in pattern or "=%[0-9A-F]{2}" in pattern

    def test_raw_schema_has_uuid_conditional(self) -> None:
        """The UUID if/then conditional is in the raw model schema."""
        raw = _raw_model_schema()
        props = raw["properties"]
        aid = props["artifact_id"]
        all_of = aid["allOf"]
        uuid_cond = [i for i in all_of if "if" in i]
        assert len(uuid_cond) == 1
        assert uuid_cond[0]["if"]["pattern"] == "^urn:[uU][uU][iI][dD]:"
        assert "pattern" in uuid_cond[0]["then"]

    def test_raw_schema_has_timestamp_range_pattern(self) -> None:
        """The timestamp pattern with numeric ranges is in the raw model schema."""
        raw = _raw_model_schema()
        props = raw["properties"]
        ca = props["created_at"]
        assert "pattern" in ca
        pattern = ca["pattern"]
        # Must have hour range
        assert "[01]" in pattern or "2[0-3]" in pattern
        # Must have minute/second range
        assert "[0-5]" in pattern

    def test_raw_schema_has_neg_zero_zero_not(self) -> None:
        """The not constraint for -00:00 is in the raw model schema."""
        raw = _raw_model_schema()
        props = raw["properties"]
        ca = props["created_at"]
        assert "not" in ca
        assert "pattern" in ca["not"]

    def test_raw_schema_has_format_date_time(self) -> None:
        """format: date-time is in the raw model schema."""
        raw = _raw_model_schema()
        props = raw["properties"]
        ca = props["created_at"]
        assert ca.get("format") == "date-time"

    def test_raw_schema_all_globalid_fields_have_allOf(self) -> None:
        """Every GlobalId field — including $defs nested — has the allOf constraint."""
        raw = _raw_model_schema()
        # Top-level
        for field in ["artifact_id", "project_id"]:
            assert "allOf" in raw["properties"][field], f"{field} missing allOf"
        # $defs
        defs = raw.get("$defs", {})
        # ProducerIdentity
        pi = defs.get("ProducerIdentity", {}).get("properties", {})
        assert "allOf" in pi.get("actor_id", {})
        run_id = pi.get("run_id", {}).get("anyOf", [{}])
        if len(run_id) > 1:
            assert "allOf" in run_id[0], "run_id anyOf[0] missing allOf"
        # PolicyReference
        pol = defs.get("PolicyReference", {}).get("properties", {})
        assert "allOf" in pol.get("policy_id", {})
        # Provenance
        prov = defs.get("Provenance", {}).get("properties", {})
        items = prov.get("parent_artifact_ids", {}).get("items", {})
        assert "allOf" in items


class TestExporterDoesNotMutateBusinessConstraints:
    """FIX3-BP-07: Exporter post-processing does not mutate business constraints."""

    def _get_business_keys(self, d: dict[str, Any], prefix: str = "") -> set[tuple[str, str]]:
        """Recursively find all business constraint keys in a schema dict."""
        business_keys = {
            "pattern",
            "required",
            "const",
            "enum",
            "allOf",
            "if",
            "then",
            "not",
            "format",
            "additionalProperties",
            "minLength",
            "maxLength",
        }
        result: set[tuple[str, str]] = set()
        for key, val in d.items():
            if key in business_keys:
                val_str = json.dumps(val, sort_keys=True)
                result.add((f"{prefix}.{key}", val_str))
            if isinstance(val, dict):
                result |= self._get_business_keys(val, f"{prefix}.{key}")
            elif isinstance(val, list):
                for i, item in enumerate(val):
                    if isinstance(item, dict):
                        result |= self._get_business_keys(item, f"{prefix}.{key}[{i}]")
        return result

    def test_exporter_preserves_all_business_constraints(self) -> None:
        """The exporter does not add, remove, or modify any business constraint."""
        raw = _raw_model_schema()
        exported = cast(dict[str, Any], _build_envelope_schema())

        raw_keys = self._get_business_keys(raw)
        exported_keys = self._get_business_keys(exported)

        # Every business key in raw must be present in exported (no removal)
        removed = raw_keys - exported_keys
        assert removed == set(), f"Exporter removed business constraints: {removed}"

        # No new business keys added by exporter
        added = exported_keys - raw_keys
        assert added == set(), f"Exporter added business constraints: {added}"

    def test_exporter_adds_only_stable_metadata(self) -> None:
        """The exporter only adds $schema, $id, title, description keys."""
        raw = _raw_model_schema()
        exported = cast(dict[str, Any], _build_envelope_schema())

        # Keys present in exported but not in raw
        added_keys = set(exported.keys()) - set(raw.keys())
        # Should only be $schema, $id (title/description may already exist)
        stable_keys = {"$schema", "$id", "title", "description"}
        non_stable = added_keys - stable_keys
        assert non_stable == set(), f"Exporter added non-stable top-level keys: {non_stable}"
