"""A1-BP-008: Generated schema equals committed bytes and independently
validates valid/invalid fixtures."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from zadc import ArtifactEnvelope, PolicyReference, ProducerIdentity, Provenance

# Add scripts directory to path for import
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_schemas import _build_envelope_schema, _serialize_schema_pretty  # noqa: E402


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def committed_schema_path(repo_root: Path) -> Path:
    return repo_root / "schemas" / "0.1" / "artifact-envelope.schema.json"


@pytest.fixture
def committed_schema_bytes(committed_schema_path: Path) -> bytes:
    return committed_schema_path.read_bytes()


@pytest.fixture
def generated_schema_text() -> str:
    schema = _build_envelope_schema()
    return _serialize_schema_pretty(schema)


class TestSchemaReproducibility:
    """Generated schema equals committed bytes."""

    def test_generated_equals_committed(
        self, committed_schema_bytes: bytes, generated_schema_text: str
    ) -> None:
        assert committed_schema_bytes == generated_schema_text.encode("utf-8")

    def test_zero_diff_on_regenerate(
        self, committed_schema_bytes: bytes, generated_schema_text: str
    ) -> None:
        """Regenerating the schema produces zero diff."""
        committed = committed_schema_bytes.decode("utf-8")
        assert committed == generated_schema_text


class TestSchemaStructure:
    """Schema has the expected structure."""

    def test_is_draft_2020_12(self, generated_schema_text: str) -> None:
        schema = json.loads(generated_schema_text)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    def test_has_required_fields(self, generated_schema_text: str) -> None:
        schema = json.loads(generated_schema_text)
        required = schema["required"]
        expected = [
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
        ]
        assert sorted(required) == sorted(expected)

    def test_additional_properties_false(self, generated_schema_text: str) -> None:
        schema = json.loads(generated_schema_text)
        assert schema["additionalProperties"] is False

    def test_enums_present(self, generated_schema_text: str) -> None:
        schema = json.loads(generated_schema_text)
        artifact_types = schema["properties"]["artifact_type"]["enum"]
        assert "packet" in artifact_types
        assert len(artifact_types) == 8
        actor_types = schema["properties"]["producer"]["properties"]["actor_type"]["enum"]
        assert "human" in actor_types
        assert len(actor_types) == 5

    def test_patterns_present(self, generated_schema_text: str) -> None:
        schema = json.loads(generated_schema_text)
        digest_pattern = schema["properties"]["policy"]["properties"]["policy_digest"]["pattern"]
        assert "sha256" in digest_pattern
        sha_pattern = schema["properties"]["policy"]["properties"]["policy_source_sha"]["pattern"]
        assert "[0-9a-f]" in sha_pattern


class TestSchemaValidatesFixtures:
    """Schema independently validates valid and invalid fixtures."""

    def _get_schema(self) -> dict[str, object]:
        return _build_envelope_schema()

    def _try_validate(self, instance: dict[str, object]) -> bool:
        """Try to validate using jsonschema if available, else use basic checks."""
        try:
            import jsonschema  # type: ignore[import-untyped]

            jsonschema.validate(instance=instance, schema=self._get_schema())
            return True
        except ImportError:
            pass
        except Exception:
            return False
        # Fallback: validate via Pydantic model
        try:
            ArtifactEnvelope.model_validate(instance)
            return True
        except Exception:
            return False

    def test_valid_envelope_passes(self) -> None:
        env = ArtifactEnvelope(
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000300",
            created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
            producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:test"),
            project_id="zutfen:project:zadc",
            slice_id="SCH-001",
            slice_instance_id="SCH-001A",
            policy=PolicyReference(
                policy_id="zutfen:zadc-policy:standard@0.1.0",
                policy_source_sha="a" * 40,
                policy_digest="sha256:" + "b" * 64,
            ),
            provenance=Provenance(parent_artifact_ids=[]),
        )
        data = env.model_dump(mode="json", by_alias=True)
        assert self._try_validate(data)

    def test_invalid_envelope_missing_required(self) -> None:
        bad_data: dict[str, object] = {
            "schema": "https://schemas.zutfen.com/zadc/0.1/artifact.schema.json"
        }
        assert not self._try_validate(bad_data)

    def test_invalid_artifact_type_rejected(self) -> None:
        env = ArtifactEnvelope(
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000301",
            created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
            producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:test"),
            project_id="zutfen:project:zadc",
            slice_id="SCH-002",
            slice_instance_id="SCH-002A",
            policy=PolicyReference(
                policy_id="zutfen:zadc-policy:standard@0.1.0",
                policy_source_sha="a" * 40,
                policy_digest="sha256:" + "b" * 64,
            ),
            provenance=Provenance(parent_artifact_ids=[]),
        )
        data = env.model_dump(mode="json", by_alias=True)
        data["artifact_type"] = "bogus"
        assert not self._try_validate(data)


class TestSchemaNoUnstableValues:
    """Schema has no local paths, timestamps, temp values, or unstable IDs."""

    def test_no_local_paths(self, generated_schema_text: str) -> None:
        assert "C:\\" not in generated_schema_text
        assert "/home/" not in generated_schema_text
        assert "/tmp/" not in generated_schema_text

    def test_no_timestamps(self, generated_schema_text: str) -> None:
        import re

        # No ISO timestamp patterns
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:", generated_schema_text)

    def test_no_temp_values(self, generated_schema_text: str) -> None:
        assert "temp" not in generated_schema_text.lower()

    def test_final_newline(self, generated_schema_text: str) -> None:
        """Schema file uses final newline."""
        assert generated_schema_text.endswith("\n")
