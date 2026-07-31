"""FIX2-BP-06: Independent timestamp schema enforcement.

Tests that the committed schema includes type string, format date-time,
and the exact ZADC timestamp pattern, and that Draft202012Validator with
FormatChecker accepts valid fixtures and rejects malformed ones.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "0.1" / "artifact-envelope.schema.json"


@pytest.fixture
def committed_schema() -> dict[str, Any]:
    result: dict[str, Any] = json.loads(_SCHEMA_PATH.read_text())
    return result


@pytest.fixture
def validator_with_format_checker(
    committed_schema: dict[str, Any],
) -> Draft202012Validator:
    return Draft202012Validator(committed_schema, format_checker=FormatChecker())


def _make_valid_data() -> dict[str, Any]:
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


class TestSchemaTimestampMetadata:
    """Committed schema includes type string, format date-time, and the exact pattern."""

    def test_created_at_is_type_string(self, committed_schema: dict[str, Any]) -> None:
        props = committed_schema["properties"]
        assert props["created_at"]["type"] == "string"

    def test_created_at_has_format_date_time(self, committed_schema: dict[str, Any]) -> None:
        props = committed_schema["properties"]
        assert props["created_at"]["format"] == "date-time"

    def test_created_at_has_exact_pattern(self, committed_schema: dict[str, Any]) -> None:
        props = committed_schema["properties"]
        pattern = props["created_at"]["pattern"]
        # The pattern must contain the key ZADC timestamp elements
        # FIX3-B: pattern now uses numeric ranges ([01]\d|2[0-3] etc.)
        assert "\\d{4}-\\d{2}-\\d{2}T" in pattern
        assert "[01]\\d|2[0-3]" in pattern  # hour range
        assert "[0-5]\\d" in pattern  # minute/second range
        assert "\\.\\d{1,6}" in pattern
        assert "Z" in pattern
        assert "[+-]" in pattern


class TestIndependentTimestampAcceptance:
    """Draft202012Validator with FormatChecker accepts every valid canonical timestamp."""

    @pytest.mark.parametrize(
        "ts",
        [
            "2026-07-31T12:00:00Z",
            "2026-07-31T17:30:00+05:30",
            "2026-07-31T07:00:00-05:00",
            "2026-07-31T12:00:00.1Z",
            "2026-07-31T12:00:00.123456Z",
            "2026-07-31T12:00:00+00:00",
        ],
    )
    def test_accept_valid_timestamp(
        self,
        validator_with_format_checker: Draft202012Validator,
        ts: str,
    ) -> None:
        data = _make_valid_data()
        data["created_at"] = ts
        errors = list(validator_with_format_checker.iter_errors(data))
        assert errors == [], f"Expected no errors for {ts}, got: {errors}"


class TestIndependentTimestampRejection:
    """The independent validator rejects every FIX2-BP-05 malformed timestamp fixture."""

    @pytest.mark.parametrize(
        "bad_ts",
        [
            # Space separators
            "2026-07-31 12:00:00Z",
            # Arbitrary separator
            "2026-07-31X12:00:00Z",
            # Basic forms
            "20260731T120000Z",
            # Week dates
            "2026-W31-1T12:00:00Z",
            # Ordinal dates
            "2026-212T12:00:00Z",
            # Offsets without colon
            "2026-07-31T12:00:00+0500",
            # Timezone-free
            "2026-07-31T12:00:00",
            # Lowercase t/z
            "2026-07-31t12:00:00Z",
            "2026-07-31T12:00:00z",
            # >6 fractional digits
            "2026-07-31T12:00:00.1234567Z",
            # Trailing data
            "2026-07-31T12:00:00Z extra",
        ],
    )
    def test_reject_malformed_timestamp(
        self,
        validator_with_format_checker: Draft202012Validator,
        bad_ts: str,
    ) -> None:
        data = _make_valid_data()
        data["created_at"] = bad_ts
        errors = list(validator_with_format_checker.iter_errors(data))
        assert len(errors) > 0, f"Expected errors for {bad_ts!r}, got none"
