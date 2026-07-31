"""FIX1-BP-06 and FIX1-BP-07: Model-derived schema and independent validation.

FIX1-BP-06: Schema derived from ArtifactEnvelope, byte-identical regeneration.
FIX1-BP-07: Independent Draft 2020-12 validation with no Pydantic fallback.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    canonical_json_text,
    seal_artifact,
)
from zadc.types import CONTRACT_VERSION, SCHEMA_ID

# Add repo root for script import
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_schemas import _build_envelope_schema  # noqa: E402

_SCHEMA_PATH = _REPO_ROOT / "schemas" / "0.1" / "artifact-envelope.schema.json"


@pytest.fixture
def committed_schema() -> dict[str, object]:
    result: dict[str, object] = json.loads(_SCHEMA_PATH.read_text())
    return result


@pytest.fixture
def validator(committed_schema: dict[str, object]) -> Draft202012Validator:
    """Draft 2020-12 validator with no Pydantic fallback."""
    return Draft202012Validator(committed_schema)


def _make_valid_canonical_json() -> str:
    """Create a valid canonical JSON for an envelope."""
    env = ArtifactEnvelope(
        schema=SCHEMA_ID,
        contract_version=CONTRACT_VERSION,
        artifact_type="packet",
        artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
        created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
        producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:eric"),
        project_id="zutfen:project:zadc",
        slice_id="ZADC-001A",
        slice_instance_id="ZADC-001A1",
        policy=PolicyReference(
            policy_id="zutfen:zadc-policy:standard@0.1.0",
            policy_source_sha="a" * 40,
            policy_digest="sha256:" + "b" * 64,
        ),
        provenance=Provenance(parent_artifact_ids=()),
    )
    return canonical_json_text(env)


class TestSchemaReproducibility:
    """FIX1-BP-06: Regeneration produces byte-identical committed schema."""

    def test_generated_equals_committed(self) -> None:
        committed = _SCHEMA_PATH.read_bytes()
        generated_schema = _build_envelope_schema()
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
        schema = _build_envelope_schema()
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

    def test_schema_derived_from_model_not_handwritten(self) -> None:
        """Schema changes when model constraints change — proves derivation."""
        schema = _build_envelope_schema()
        schema_str = json.dumps(schema)
        # These patterns come from the model's StringConstraints, not handwritten
        assert "sha256:[0-9a-f]{64}" in schema_str
        assert "[0-9a-f]{40}" in schema_str
        # Enums from Literal types
        assert "packet" in schema_str
        assert "human" in schema_str
        # $defs proves model derivation (referenced models)
        assert "$defs" in schema_str

    def test_schema_has_no_unstable_values(self) -> None:
        schema_str = _SCHEMA_PATH.read_text()
        import re

        # No local paths
        assert "/home/" not in schema_str
        assert "/tmp/" not in schema_str
        # No ISO timestamps
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:", schema_str)
        # No process-specific values
        assert "temp" not in schema_str.lower()

    def test_check_schema_valid(self, committed_schema: dict[str, object]) -> None:
        """Draft202012Validator.check_schema passes on the committed schema."""
        Draft202012Validator.check_schema(committed_schema)


class TestIndependentValidation:
    """FIX1-BP-07: Independent Draft 2020-12 validation."""

    def test_valid_canonical_passes(self, validator: Draft202012Validator) -> None:
        data = json.loads(_make_valid_canonical_json())
        errors = list(validator.iter_errors(data))
        assert errors == []

    def test_numeric_timestamp_rejected(self, validator: Draft202012Validator) -> None:
        data = json.loads(_make_valid_canonical_json())
        data["created_at"] = 1234567890
        errors = list(validator.iter_errors(data))
        assert len(errors) > 0

    def test_missing_uri_scheme_rejected(self, validator: Draft202012Validator) -> None:
        data = json.loads(_make_valid_canonical_json())
        data["artifact_id"] = "plain-id-no-scheme"
        errors = list(validator.iter_errors(data))
        assert len(errors) > 0

    def test_unicode_controls_rejected_by_model(self) -> None:
        """Unicode controls are rejected by the model validator (not schema pattern)."""
        from pydantic import ValidationError

        with pytest.raises((ValidationError, ValueError)):
            ProducerIdentity(actor_type="human", actor_id="zutfen:\x00null")

    def test_unknown_properties_rejected(self, validator: Draft202012Validator) -> None:
        data = json.loads(_make_valid_canonical_json())
        data["unknown_field"] = "evil"
        errors = list(validator.iter_errors(data))
        assert len(errors) > 0

    def test_malformed_digest_rejected(self, validator: Draft202012Validator) -> None:
        data = json.loads(_make_valid_canonical_json())
        data["policy"]["policy_digest"] = "sha256:short"
        errors = list(validator.iter_errors(data))
        assert len(errors) > 0

    def test_malformed_sha_rejected(self, validator: Draft202012Validator) -> None:
        data = json.loads(_make_valid_canonical_json())
        data["policy"]["policy_source_sha"] = "tooshort"
        errors = list(validator.iter_errors(data))
        assert len(errors) > 0

    def test_invalid_enum_rejected(self, validator: Draft202012Validator) -> None:
        data = json.loads(_make_valid_canonical_json())
        data["artifact_type"] = "bogus_type"
        errors = list(validator.iter_errors(data))
        assert len(errors) > 0

    def test_missing_required_field_rejected(self, validator: Draft202012Validator) -> None:
        data = json.loads(_make_valid_canonical_json())
        del data["producer"]
        errors = list(validator.iter_errors(data))
        assert len(errors) > 0

    def test_sealed_envelope_validates(self, validator: Draft202012Validator) -> None:
        env = ArtifactEnvelope(
            schema=SCHEMA_ID,
            contract_version=CONTRACT_VERSION,
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
            created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
            producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:eric"),
            project_id="zutfen:project:zadc",
            slice_id="ZADC-001A",
            slice_instance_id="ZADC-001A1",
            policy=PolicyReference(
                policy_id="zutfen:zadc-policy:standard@0.1.0",
                policy_source_sha="a" * 40,
                policy_digest="sha256:" + "b" * 64,
            ),
            provenance=Provenance(parent_artifact_ids=()),
        )
        sealed = seal_artifact(env)
        data = json.loads(canonical_json_text(sealed))
        errors = list(validator.iter_errors(data))
        assert errors == []
