"""FIX2-BP-01: Required common-envelope fields.

Tests that schema, contract_version, and provenance.parent_artifact_ids
are required at runtime and in the generated schema, with exact const values.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]
from pydantic import ValidationError

from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    canonical_json_text,
)
from zadc.types import CONTRACT_VERSION, SCHEMA_ID

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


_SCHEMA_PATH = _REPO_ROOT / "schemas" / "0.1" / "artifact-envelope.schema.json"


def _make_valid_data() -> dict[str, Any]:
    """Create a valid canonical JSON data dict for an envelope."""
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
    return cast(dict[str, Any], json.loads(canonical_json_text(env)))


@pytest.fixture
def committed_schema() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_SCHEMA_PATH.read_text()))


@pytest.fixture
def validator_with_format_checker(
    committed_schema: dict[str, Any],
) -> Draft202012Validator:
    """Draft 2020-12 validator WITH explicit FormatChecker."""
    return Draft202012Validator(committed_schema, format_checker=FormatChecker())


# ---------------------------------------------------------------------------
# Runtime rejection: missing required fields
# ---------------------------------------------------------------------------


class TestRuntimeRejectsMissingFields:
    """Runtime rejects missing schema, contract_version, and parent_artifact_ids."""

    def test_runtime_rejects_missing_schema(self) -> None:
        data = _make_valid_data()
        del data["schema"]
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)

    def test_runtime_rejects_missing_contract_version(self) -> None:
        data = _make_valid_data()
        del data["contract_version"]
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)

    def test_runtime_rejects_missing_parent_artifact_ids(self) -> None:
        data = _make_valid_data()
        del data["provenance"]["parent_artifact_ids"]
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)


# ---------------------------------------------------------------------------
# Runtime rejection: wrong values
# ---------------------------------------------------------------------------


class TestRuntimeRejectsWrongValues:
    """Runtime rejects wrong schema URI and contract version."""

    def test_runtime_rejects_wrong_schema_uri(self) -> None:
        data = _make_valid_data()
        data["schema"] = "https://wrong.example/schema.json"
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)

    def test_runtime_rejects_wrong_contract_version(self) -> None:
        data = _make_valid_data()
        data["contract_version"] = "0.2.0"
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)


# ---------------------------------------------------------------------------
# Schema: required + const entries
# ---------------------------------------------------------------------------


class TestSchemaRequiredAndConst:
    """Generated schema marks all fields required and emits exact const values."""

    def test_schema_marks_schema_required(self, committed_schema: dict[str, Any]) -> None:
        required = committed_schema["required"]
        assert "schema" in required

    def test_schema_marks_contract_version_required(self, committed_schema: dict[str, Any]) -> None:
        required = committed_schema["required"]
        assert "contract_version" in required

    def test_schema_emits_schema_const(self, committed_schema: dict[str, Any]) -> None:
        props = committed_schema["properties"]
        assert props["schema"]["const"] == SCHEMA_ID

    def test_schema_emits_contract_version_const(self, committed_schema: dict[str, Any]) -> None:
        props = committed_schema["properties"]
        assert props["contract_version"]["const"] == CONTRACT_VERSION

    def test_schema_marks_parent_artifact_ids_required(
        self, committed_schema: dict[str, Any]
    ) -> None:
        prov_def = committed_schema["$defs"]["Provenance"]
        assert "parent_artifact_ids" in prov_def["required"]


# ---------------------------------------------------------------------------
# Independent schema rejection
# ---------------------------------------------------------------------------


class TestIndependentSchemaRejection:
    """Independent Draft202012Validator + FormatChecker rejects every missing/wrong case."""

    def test_rejects_missing_schema(
        self, validator_with_format_checker: Draft202012Validator
    ) -> None:
        data = _make_valid_data()
        del data["schema"]
        errors = list(validator_with_format_checker.iter_errors(data))
        assert len(errors) > 0

    def test_rejects_wrong_schema(
        self, validator_with_format_checker: Draft202012Validator
    ) -> None:
        data = _make_valid_data()
        data["schema"] = "https://wrong.example/schema.json"
        errors = list(validator_with_format_checker.iter_errors(data))
        assert len(errors) > 0

    def test_rejects_missing_contract_version(
        self, validator_with_format_checker: Draft202012Validator
    ) -> None:
        data = _make_valid_data()
        del data["contract_version"]
        errors = list(validator_with_format_checker.iter_errors(data))
        assert len(errors) > 0

    def test_rejects_wrong_contract_version(
        self, validator_with_format_checker: Draft202012Validator
    ) -> None:
        data = _make_valid_data()
        data["contract_version"] = "0.2.0"
        errors = list(validator_with_format_checker.iter_errors(data))
        assert len(errors) > 0

    def test_rejects_missing_parent_artifact_ids(
        self, validator_with_format_checker: Draft202012Validator
    ) -> None:
        data = _make_valid_data()
        del data["provenance"]["parent_artifact_ids"]
        errors = list(validator_with_format_checker.iter_errors(data))
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Root provenance with empty parent array
# ---------------------------------------------------------------------------


class TestRootProvenanceEmptyArray:
    """Valid root provenance explicitly uses an empty parent array."""

    def test_empty_parent_array_accepted_runtime(self) -> None:
        prov = Provenance(parent_artifact_ids=())
        assert prov.parent_artifact_ids == ()

    def test_empty_parent_array_accepted_schema(
        self, validator_with_format_checker: Draft202012Validator
    ) -> None:
        data = _make_valid_data()
        errors = list(validator_with_format_checker.iter_errors(data))
        assert errors == []
