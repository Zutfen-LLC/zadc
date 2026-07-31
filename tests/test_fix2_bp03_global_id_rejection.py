"""FIX2-BP-03: Canonical GlobalId rejection.

Tests that malformed, noncanonical, and unsafe URI forms are rejected by
the runtime, with matching independent JSON Schema rejection cases for
every constraint represented by the schema.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from zadc.types import validate_global_id

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "0.1" / "artifact-envelope.schema.json"


@pytest.fixture
def validator_with_format_checker() -> Draft202012Validator:
    schema = json.loads(_SCHEMA_PATH.read_text())
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _make_valid_data() -> dict[str, Any]:
    """Create a valid data dict with a valid GlobalId to mutate."""
    return {
        "schema": "https://schemas.zutfen.com/zadc/0.1/artifact.schema.json",
        "contract_version": "0.1.0",
        "artifact_type": "packet",
        "artifact_id": "urn:uuid:00000000-0000-0000-0000-000000000001",
        "created_at": "2026-07-31T12:00:00Z",
        "producer": {
            "actor_type": "human",
            "actor_id": "zutfen:human:eric",
        },
        "project_id": "zutfen:project:zadc",
        "slice_id": "ZADC-001A",
        "slice_instance_id": "ZADC-001A1",
        "policy": {
            "policy_id": "zutfen:zadc-policy:standard@0.1.0",
            "policy_source_sha": "a" * 40,
            "policy_digest": "sha256:" + "b" * 64,
        },
        "provenance": {"parent_artifact_ids": []},
    }


# ---------------------------------------------------------------------------
# Runtime rejections
# ---------------------------------------------------------------------------


class TestRuntimeGlobalIdRejection:
    """Runtime rejects invalid and noncanonical URI forms."""

    @pytest.mark.parametrize(
        "bad_value",
        [
            # No scheme
            "plain-identifier",
            # Uppercase scheme
            "URN:uuid:00000000-0000-0000-0000-000000000001",
            "HTTPS://example.com/path",
            # Empty scheme-specific part
            "https:",
            "custom:",
            "zutfen:",
            # Raw spaces
            "zutfen: human:eric",
            "zutfen:human eric",
            # Tabs and newlines
            "zutfen:human\t",
            "zutfen:human\n",
            # Backslashes
            "zutfen:human\\eric",
            # Raw Unicode
            "zutfen:héllo",
            "custom:café",
            # Unicode category-C values (ASCII control)
            "zutfen:\x00null",
            # Malformed percent escapes
            "https://example.com/%GG",
            "https://example.com/%2",
            "https://example.com/%",
            # Lowercase percent escapes
            "https://example.com/%2fpath",
            "https://example.com/path%20with%2fslash",
        ],
    )
    def test_reject_invalid_global_ids(self, bad_value: str) -> None:
        with pytest.raises((ValueError, TypeError)):
            validate_global_id(bad_value)

    @pytest.mark.parametrize(
        "bad_uuid",
        [
            # Malformed UUID
            "urn:uuid:not-a-uuid",
            # Uppercase prefix
            "URN:UUID:00000000-0000-0000-0000-000000000001",
            # Uppercase hex
            "urn:uuid:ABCDEF00-0000-0000-0000-000000000000",
            "urn:uuid:00000000-0000-0000-0000-00000000000A",
            # Unhyphenated
            "urn:uuid:000000000000000000000000000000",
            "urn:uuid:000000000000000000000000000000000000",
            # Braced
            "urn:uuid:{00000000-0000-0000-0000-000000000001}",
            # Noncanonical (uppercase urn prefix is caught by scheme check)
            "urn:uuid:00000000-0000-0000-0000-00000000000g",
        ],
    )
    def test_reject_noncanonical_uuid_urns(self, bad_uuid: str) -> None:
        with pytest.raises((ValueError, TypeError)):
            validate_global_id(bad_uuid)

    def test_reject_no_scheme(self) -> None:
        with pytest.raises(ValueError):
            validate_global_id("plain-identifier")

    def test_reject_empty_scheme_specific(self) -> None:
        with pytest.raises(ValueError):
            validate_global_id("https:")

    def test_reject_another_scheme_empty(self) -> None:
        with pytest.raises(ValueError):
            validate_global_id("custom:")


# ---------------------------------------------------------------------------
# Independent JSON Schema rejection cases
# ---------------------------------------------------------------------------


class TestIndependentSchemaGlobalIdRejection:
    """Independent JSON Schema rejection for constraints representable by the schema."""

    def test_rejects_no_scheme(self, validator_with_format_checker: Draft202012Validator) -> None:
        """The pattern requires scheme:colon:something, so no-scheme fails."""
        data = _make_valid_data()
        data["artifact_id"] = "plain-identifier"
        errors = list(validator_with_format_checker.iter_errors(data))
        assert len(errors) > 0

    def test_rejects_uppercase_scheme(
        self, validator_with_format_checker: Draft202012Validator
    ) -> None:
        """Uppercase scheme fails the lowercase pattern."""
        data = _make_valid_data()
        data["artifact_id"] = "URN:uuid:00000000-0000-0000-0000-000000000001"
        errors = list(validator_with_format_checker.iter_errors(data))
        assert len(errors) > 0

    def test_rejects_empty_ssp(self, validator_with_format_checker: Draft202012Validator) -> None:
        """Empty scheme-specific part fails the + quantifier."""
        data = _make_valid_data()
        data["artifact_id"] = "https:"
        errors = list(validator_with_format_checker.iter_errors(data))
        assert len(errors) > 0
