"""FIX3-BP-01 through FIX3-BP-06: Complete runtime/schema parity matrix.

This file implements the comprehensive parity matrix required by FIX3-BP-06:
every portable GlobalId and Timestamp acceptance/rejection case is run
through BOTH runtime validation AND the committed schema (Draft202012Validator
with FormatChecker), and the outcomes must match.

FIX3-BP-01: Percent-aware GlobalId schema acceptance
FIX3-BP-02: Percent-aware GlobalId schema rejection
FIX3-BP-03: Canonical UUID URN conditional
FIX3-BP-04: Timestamp schema numeric ranges
FIX3-BP-05: Unknown offset and calendar parity
FIX3-BP-06: Complete runtime/schema parity matrix
"""

import json
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from zadc.types import validate_global_id, validate_timestamp

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "0.1" / "artifact-envelope.schema.json"


@pytest.fixture
def committed_schema() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_SCHEMA_PATH.read_text()))


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
        "producer": {"actor_type": "human", "actor_id": "zutfen:human:eric"},
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


def _runtime_accepts_global_id(value: str) -> bool:
    try:
        validate_global_id(value)
        return True
    except (ValueError, TypeError):
        return False


def _schema_accepts_global_id(validator: Draft202012Validator, field_path: str, value: str) -> bool:
    """Test if the schema accepts a GlobalId value at a given field path."""
    data = _make_valid_data()
    parts = field_path.split(".")
    d = data
    for p in parts[:-1]:
        d = d[p]
    d[parts[-1]] = value
    errors = list(validator.iter_errors(data))
    return len(errors) == 0


def _runtime_accepts_timestamp(value: str) -> bool:
    try:
        validate_timestamp(value)
        return True
    except (ValueError, TypeError):
        return False


def _schema_accepts_timestamp(validator: Draft202012Validator, value: str) -> bool:
    data = _make_valid_data()
    data["created_at"] = value
    errors = list(validator.iter_errors(data))
    return len(errors) == 0


# ---------------------------------------------------------------------------
# FIX3-BP-01: Percent-aware GlobalId schema acceptance
# ---------------------------------------------------------------------------


class TestFix3BP01PercentAwareAcceptance:
    """FIX3-BP-01: Runtime and independent schema accept valid percent escapes."""

    @pytest.mark.parametrize(
        "value",
        [
            # Unescaped RFC 3986 characters
            "zutfen:human:eric",
            "github:Zutfen-LLC/zadc",
            "https://example.com/path?query=value&other=2",
            "custom:resource_name-1.0",
            "custom:path/to/resource",
            "custom:key=value",
            # Valid uppercase percent escapes
            "https://example.com/path%20with%20spaces",
            "custom:caf%C3%A9",
            "https://example.com/%2Fpath%3F",
            "https://example.com/%5Barray%5D",
            # Multibyte UTF-8 as uppercase escapes
            "custom:%E2%9C%93check",
            "custom:%E4%B8%AD%E6%96%87",
            # Another lowercase custom scheme
            "myapp:resource-id-123",
        ],
    )
    def test_runtime_accepts_valid_global_ids(self, value: str) -> None:
        assert _runtime_accepts_global_id(value), f"Runtime should accept {value!r}"

    @pytest.mark.parametrize(
        "value",
        [
            "zutfen:human:eric",
            "github:Zutfen-LLC/zadc",
            "https://example.com/path?query=value",
            "custom:caf%C3%A9",
            "https://example.com/%2Fpath",
            "custom:%E2%9C%93",
            "myapp:resource-id",
        ],
    )
    def test_schema_accepts_valid_global_ids(
        self,
        validator_with_format_checker: Draft202012Validator,
        value: str,
    ) -> None:
        assert _schema_accepts_global_id(validator_with_format_checker, "artifact_id", value), (
            f"Schema should accept {value!r}"
        )

    def test_accepted_canonical_serializes_unchanged(self) -> None:
        """Accepted canonical GlobalIds serialize byte-for-byte unchanged."""
        for value in [
            "urn:uuid:00000000-0000-0000-0000-000000000001",
            "zutfen:human:eric",
            "https://example.com/path%20with",
        ]:
            assert validate_global_id(value) == value


# ---------------------------------------------------------------------------
# FIX3-BP-02: Percent-aware GlobalId schema rejection
# ---------------------------------------------------------------------------


class TestFix3BP02PercentAwareRejection:
    """FIX3-BP-02: Runtime and independent schema reject malformed percent escapes."""

    @pytest.mark.parametrize(
        "bad_value",
        [
            "custom:path%",  # bare %
            "custom:path%2",  # incomplete escape
            "custom:path%GG",  # non-hex escape
            "custom:path%2g",  # lowercase hex in second position
            "custom:path%2f",  # lowercase hex
            "custom:path%0a",  # lowercase hex
            "custom:valid%20and%",  # trailing incomplete
            "custom:mix%20valid%2g",  # mixed validity
        ],
    )
    def test_runtime_rejects_malformed_escapes(self, bad_value: str) -> None:
        assert not _runtime_accepts_global_id(bad_value), f"Runtime should reject {bad_value!r}"

    @pytest.mark.parametrize(
        "bad_value",
        [
            "custom:path%",
            "custom:path%2",
            "custom:path%GG",
            "custom:path%2g",
            "custom:path%2f",
            "custom:path%0a",
            "custom:valid%20and%",
            "custom:mix%20valid%2g",
        ],
    )
    def test_schema_rejects_malformed_escapes_artifact_id(
        self,
        validator_with_format_checker: Draft202012Validator,
        bad_value: str,
    ) -> None:
        assert not _schema_accepts_global_id(
            validator_with_format_checker, "artifact_id", bad_value
        ), f"Schema should reject {bad_value!r} at artifact_id"

    def test_schema_rejects_at_nested_producer_actor_id(
        self,
        validator_with_format_checker: Draft202012Validator,
    ) -> None:
        """Rejection works on nested actor_id."""
        assert not _schema_accepts_global_id(
            validator_with_format_checker, "producer.actor_id", "custom:path%2f"
        )

    def test_schema_rejects_at_nested_policy_id(
        self,
        validator_with_format_checker: Draft202012Validator,
    ) -> None:
        """Rejection works on nested policy_id."""
        assert not _schema_accepts_global_id(
            validator_with_format_checker, "policy.policy_id", "custom:path%"
        )

    def test_schema_rejects_at_parent_artifact_ids_item(
        self,
        validator_with_format_checker: Draft202012Validator,
    ) -> None:
        """Rejection works on parent_artifact_ids array items."""
        data = _make_valid_data()
        data["provenance"]["parent_artifact_ids"] = ["custom:path%2f"]
        errors = list(validator_with_format_checker.iter_errors(data))
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# FIX3-BP-03: Canonical UUID URN conditional
# ---------------------------------------------------------------------------


class TestFix3BP03UUIDConditional:
    """FIX3-BP-03: Runtime and schema enforce canonical UUID URN via if/then conditional."""

    @pytest.mark.parametrize(
        "value",
        [
            "urn:uuid:00000000-0000-0000-0000-000000000001",
            "urn:uuid:abcdef01-2345-6789-abcd-ef0123456789",
        ],
    )
    def test_runtime_accepts_canonical_uuid_urn(self, value: str) -> None:
        assert _runtime_accepts_global_id(value)

    @pytest.mark.parametrize(
        "value",
        [
            "urn:uuid:00000000-0000-0000-0000-000000000001",
            "urn:uuid:abcdef01-2345-6789-abcd-ef0123456789",
        ],
    )
    def test_schema_accepts_canonical_uuid_urn(
        self,
        validator_with_format_checker: Draft202012Validator,
        value: str,
    ) -> None:
        assert _schema_accepts_global_id(validator_with_format_checker, "artifact_id", value)

    @pytest.mark.parametrize(
        "bad_uuid",
        [
            "urn:uuid:not-a-uuid",  # malformed text
            "URN:UUID:00000000-0000-0000-0000-000000000001",  # uppercase scheme + prefix
            "urn:UUID:00000000-0000-0000-0000-000000000001",  # mixed-case namespace UUID
            "urn:Uuid:00000000-0000-0000-0000-000000000001",  # mixed-case namespace Uuid
            "urn:uUiD:00000000-0000-0000-0000-000000000001",  # mixed-case namespace uUiD
            "urn:uuid:ABCDEF00-0000-0000-0000-000000000000",  # uppercase hex
            "urn:uuid:00000000000000000000000000000000",  # unhyphenated
            "urn:uuid:{00000000-0000-0000-0000-000000000001}",  # braced
            "urn:uuid:00000000-0000-0000-0000-0000000000",  # too short
            "urn:uuid:00000000-0000-0000-0000-000000000000000",  # too long
            "urn:uuid:00000000-0000-0000-0000-00000000000g",  # invalid hex
        ],
    )
    def test_runtime_rejects_noncanonical_uuid(self, bad_uuid: str) -> None:
        assert not _runtime_accepts_global_id(bad_uuid)

    @pytest.mark.parametrize(
        "bad_uuid",
        [
            "urn:uuid:not-a-uuid",
            "URN:UUID:00000000-0000-0000-0000-000000000001",
            "urn:UUID:00000000-0000-0000-0000-000000000001",
            "urn:Uuid:00000000-0000-0000-0000-000000000001",
            "urn:uUiD:00000000-0000-0000-0000-000000000001",
            "urn:uuid:ABCDEF00-0000-0000-0000-000000000000",
            "urn:uuid:00000000000000000000000000000000",
            "urn:uuid:{00000000-0000-0000-0000-000000000001}",
            "urn:uuid:00000000-0000-0000-0000-0000000000",
            "urn:uuid:00000000-0000-0000-0000-000000000000000",
            "urn:uuid:00000000-0000-0000-0000-00000000000g",
        ],
    )
    def test_schema_rejects_noncanonical_uuid(
        self,
        validator_with_format_checker: Draft202012Validator,
        bad_uuid: str,
    ) -> None:
        assert not _schema_accepts_global_id(validator_with_format_checker, "artifact_id", bad_uuid)

    def test_schema_has_uuid_conditional_in_every_globalid_path(
        self,
        committed_schema: dict[str, Any],
    ) -> None:
        """The if/then conditional is present in every GlobalId schema path."""
        schema_str = json.dumps(committed_schema)
        # The UUID conditional must be present
        assert "urn:uuid:" in schema_str
        assert '"if"' in schema_str
        assert '"then"' in schema_str

        # Check specific fields have allOf with UUID conditional
        props = committed_schema["properties"]
        for field in ["artifact_id", "project_id"]:
            field_schema = props[field]
            assert "allOf" in field_schema, f"{field} missing allOf"
            all_of = field_schema["allOf"]
            assert len(all_of) >= 2, f"{field} allOf must have base + UUID conditional"
            # Second element should have if/then for UUID
            assert "if" in all_of[1], f"{field} missing UUID if/then"

        # Check $defs
        defs = committed_schema["$defs"]
        # ProducerIdentity.actor_id
        pi = defs["ProducerIdentity"]["properties"]["actor_id"]
        assert "allOf" in pi
        assert "if" in pi["allOf"][1]
        # PolicyReference.policy_id
        pol = defs["PolicyReference"]["properties"]["policy_id"]
        assert "allOf" in pol
        assert "if" in pol["allOf"][1]
        # Provenance.parent_artifact_ids items
        pai = defs["Provenance"]["properties"]["parent_artifact_ids"]["items"]
        assert "allOf" in pai
        assert "if" in pai["allOf"][1]


# ---------------------------------------------------------------------------
# FIX3-BP-04: Timestamp schema numeric ranges
# ---------------------------------------------------------------------------


class TestFix3BP04TimestampRanges:
    """FIX3-BP-04: Schema rejects out-of-range hour, minute, second, offset values."""

    @pytest.mark.parametrize(
        "bad_ts",
        [
            "2026-07-31T24:00:00Z",  # hour 24
            "2026-07-31T12:60:00Z",  # minute 60
            "2026-07-31T12:00:60Z",  # second 60 (leap second)
            "2026-07-31T12:00:00+24:00",  # offset hour 24
            "2026-07-31T12:00:00+12:60",  # offset minute 60
        ],
    )
    def test_schema_rejects_out_of_range(
        self,
        validator_with_format_checker: Draft202012Validator,
        bad_ts: str,
    ) -> None:
        assert not _schema_accepts_timestamp(validator_with_format_checker, bad_ts)

    @pytest.mark.parametrize(
        "bad_ts",
        [
            "2026-07-31T24:00:00Z",
            "2026-07-31T12:60:00Z",
            "2026-07-31T12:00:60Z",
            "2026-07-31T12:00:00+24:00",
            "2026-07-31T12:00:00+12:60",
        ],
    )
    def test_runtime_rejects_out_of_range(self, bad_ts: str) -> None:
        assert not _runtime_accepts_timestamp(bad_ts)

    @pytest.mark.parametrize(
        "good_ts",
        [
            "2026-07-31T00:00:00Z",  # hour 00 boundary
            "2026-07-31T23:59:59Z",  # maximum time
            "2026-07-31T12:00:00+00:00",  # offset 00:00
            "2026-07-31T12:00:00+23:59",  # max offset
            "2026-07-31T12:00:00-23:59",  # max negative offset
        ],
    )
    def test_schema_accepts_valid_boundaries(
        self,
        validator_with_format_checker: Draft202012Validator,
        good_ts: str,
    ) -> None:
        assert _schema_accepts_timestamp(validator_with_format_checker, good_ts), (
            f"Schema should accept {good_ts!r}"
        )


# ---------------------------------------------------------------------------
# FIX3-BP-05: Unknown offset and calendar parity
# ---------------------------------------------------------------------------


class TestFix3BP05OffsetAndCalendar:
    """FIX3-BP-05: -00:00 and invalid calendar dates rejected by both runtime and schema."""

    def test_schema_rejects_neg_zero_offset(
        self,
        validator_with_format_checker: Draft202012Validator,
    ) -> None:
        assert not _schema_accepts_timestamp(
            validator_with_format_checker, "2026-07-31T12:00:00-00:00"
        )

    def test_runtime_rejects_neg_zero_offset(self) -> None:
        assert not _runtime_accepts_timestamp("2026-07-31T12:00:00-00:00")

    @pytest.mark.parametrize(
        "bad_date_ts",
        [
            "2025-02-29T12:00:00Z",  # Feb 29 non-leap year
            "2026-02-30T12:00:00Z",  # Feb 30
            "2026-04-31T12:00:00Z",  # Apr 31
            "2026-00-15T12:00:00Z",  # month 00
            "2026-13-15T12:00:00Z",  # month 13
            "2026-01-00T12:00:00Z",  # day 00
        ],
    )
    def test_schema_rejects_invalid_calendar_dates(
        self,
        validator_with_format_checker: Draft202012Validator,
        bad_date_ts: str,
    ) -> None:
        assert not _schema_accepts_timestamp(validator_with_format_checker, bad_date_ts)

    @pytest.mark.parametrize(
        "bad_date_ts",
        [
            "2025-02-29T12:00:00Z",
            "2026-02-30T12:00:00Z",
            "2026-04-31T12:00:00Z",
            "2026-00-15T12:00:00Z",
            "2026-13-15T12:00:00Z",
            "2026-01-00T12:00:00Z",
        ],
    )
    def test_runtime_rejects_invalid_calendar_dates(self, bad_date_ts: str) -> None:
        assert not _runtime_accepts_timestamp(bad_date_ts)

    @pytest.mark.parametrize(
        "good_date_ts",
        [
            "2024-02-29T12:00:00Z",  # Feb 29 leap year
            "2026-01-31T23:59:59Z",  # Jan 31 month-end
            "2026-12-31T23:59:59Z",  # Dec 31 month-end
            "2026-06-30T12:00:00Z",  # Jun 30 month-end
        ],
    )
    def test_schema_accepts_valid_calendar_dates(
        self,
        validator_with_format_checker: Draft202012Validator,
        good_date_ts: str,
    ) -> None:
        assert _schema_accepts_timestamp(validator_with_format_checker, good_date_ts)


# ---------------------------------------------------------------------------
# FIX3-BP-06: Complete runtime/schema parity matrix
# ---------------------------------------------------------------------------


# Combined parity table: (value, expected_accept, category)
# All cases must have matching runtime and schema outcomes.
PARITY_CASES_GLOBAL_ID: list[tuple[str, bool, str]] = [
    # Acceptance cases
    ("urn:uuid:00000000-0000-0000-0000-000000000001", True, "canonical uuid"),
    ("urn:uuid:abcdef01-2345-6789-abcd-ef0123456789", True, "canonical uuid 2"),
    ("zutfen:human:eric", True, "zutfen scheme"),
    ("github:Zutfen-LLC/zadc", True, "github scheme"),
    ("https://example.com/artifact/001", True, "https scheme"),
    ("custom:resource-id", True, "custom scheme"),
    ("custom:path%20with", True, "valid uppercase escape"),
    ("custom:caf%C3%A9", True, "multibyte uppercase escape"),
    ("https://example.com/%2Fpath", True, "uppercase slash escape"),
    ("https://example.com/path?key=val&x=1", True, "reserved chars"),
    ("custom:array[0]", True, "brackets"),
    # Rejection cases
    ("plain-no-scheme", False, "no scheme"),
    ("URN:uuid:00000000-0000-0000-0000-000000000001", False, "uppercase scheme"),
    ("https:", False, "empty SSP"),
    ("custom:", False, "empty SSP 2"),
    ("custom:path%", False, "bare percent"),
    ("custom:path%2", False, "incomplete escape"),
    ("custom:path%GG", False, "non-hex escape"),
    ("custom:path%2f", False, "lowercase hex escape"),
    ("custom:path%0a", False, "lowercase hex 2"),
    ("custom:mix%20and%", False, "trailing incomplete"),
    ("urn:uuid:not-a-uuid", False, "malformed uuid"),
    ("urn:UUID:00000000-0000-0000-0000-000000000001", False, "mixed-case namespace UUID"),
    ("urn:Uuid:00000000-0000-0000-0000-000000000001", False, "mixed-case namespace Uuid"),
    ("urn:uUiD:00000000-0000-0000-0000-000000000001", False, "mixed-case namespace uUiD"),
    ("urn:uuid:ABCDEF00-0000-0000-0000-000000000000", False, "uppercase hex uuid"),
    ("urn:uuid:00000000000000000000000000000000", False, "unhyphenated uuid"),
    ("urn:uuid:{00000000-0000-0000-0000-000000000001}", False, "braced uuid"),
    ("urn:uuid:00000000-0000-0000-0000-0000000000", False, "too short uuid"),
    ("urn:uuid:00000000-0000-0000-0000-00000000000g", False, "invalid hex uuid"),
]

PARITY_CASES_TIMESTAMP: list[tuple[str, bool, str]] = [
    # Acceptance
    ("2026-07-31T12:00:00Z", True, "UTC Z"),
    ("2026-07-31T17:30:00+05:30", True, "positive offset"),
    ("2026-07-31T07:00:00-05:00", True, "negative offset"),
    ("2026-07-31T12:00:00+00:00", True, "plus zero offset"),
    ("2026-07-31T12:00:00.1Z", True, "1-digit fraction"),
    ("2026-07-31T12:00:00.123456Z", True, "6-digit fraction"),
    ("2024-02-29T12:00:00Z", True, "leap day"),
    ("2026-01-31T23:59:59Z", True, "month-end boundary"),
    ("2026-07-31T00:00:00Z", True, "hour 00 boundary"),
    # Rejection
    ("2026-07-31 12:00:00Z", False, "space separator"),
    ("2026-07-31t12:00:00Z", False, "lowercase t"),
    ("2026-07-31T12:00:00z", False, "lowercase z"),
    ("2026-07-31T12:00:00", False, "no offset"),
    ("2026-07-31T12:00:00-00:00", False, "unknown offset -00:00"),
    ("2026-07-31T12:00:60Z", False, "leap second"),
    ("2026-07-31T24:00:00Z", False, "hour 24"),
    ("2026-07-31T12:60:00Z", False, "minute 60"),
    ("2026-07-31T12:00:00+24:00", False, "offset hour 24"),
    ("2026-07-31T12:00:00+12:60", False, "offset minute 60"),
    ("2026-02-30T12:00:00Z", False, "Feb 30"),
    ("2025-02-29T12:00:00Z", False, "Feb 29 non-leap"),
    ("2026-04-31T12:00:00Z", False, "Apr 31"),
    ("2026-13-01T12:00:00Z", False, "month 13"),
    ("2026-00-01T12:00:00Z", False, "month 00"),
    ("2026-01-00T12:00:00Z", False, "day 00"),
    ("2026-07-31T12:00:00.1234567Z", False, "7-digit fraction"),
    ("20260731T120000Z", False, "basic form"),
    ("2026-W31-1T12:00:00Z", False, "week date"),
    # Non-ASCII digits (Unicode \d bypass — must use [0-9] not \d)
    ("\u0662\u0660\u0662\u0666-07-31T12:00:00Z", False, "Arabic-Indic year digits"),
    ("2026-0\u0667-31T12:00:00Z", False, "Arabic-Indic month digit"),
    ("2026-07-31T1\u0662:00:00Z", False, "Arabic-Indic hour digit"),
    ("0000-01-01T00:00:00Z", False, "year 0000"),
]


class TestFix3BP06CompleteParityMatrix:
    """FIX3-BP-06: Every portable case has matching runtime/schema outcomes."""

    @pytest.mark.parametrize(
        ("value", "expected", "desc"),
        PARITY_CASES_GLOBAL_ID,
    )
    def test_global_id_parity(
        self,
        validator_with_format_checker: Draft202012Validator,
        value: str,
        expected: bool,
        desc: str,
    ) -> None:
        rt = _runtime_accepts_global_id(value)
        sc = _schema_accepts_global_id(validator_with_format_checker, "artifact_id", value)
        exp_str = "accept" if expected else "reject"
        rt_str = "accept" if rt else "reject"
        sc_str = "accept" if sc else "reject"
        assert rt == expected, f"RT {desc}: exp={exp_str} got={rt_str}"
        assert sc == expected, f"SC {desc}: exp={exp_str} got={sc_str}"
        assert rt == sc, f"PARITY {desc}: rt={rt_str} sc={sc_str}"

    @pytest.mark.parametrize(
        ("value", "expected", "desc"),
        PARITY_CASES_TIMESTAMP,
    )
    def test_timestamp_parity(
        self,
        validator_with_format_checker: Draft202012Validator,
        value: str,
        expected: bool,
        desc: str,
    ) -> None:
        rt = _runtime_accepts_timestamp(value)
        sc = _schema_accepts_timestamp(validator_with_format_checker, value)
        exp_str = "accept" if expected else "reject"
        rt_str = "accept" if rt else "reject"
        sc_str = "accept" if sc else "reject"
        assert rt == expected, f"RT {desc}: exp={exp_str} got={rt_str}"
        assert sc == expected, f"SC {desc}: exp={exp_str} got={sc_str}"
        assert rt == sc, f"PARITY {desc}: rt={rt_str} sc={sc_str}"
