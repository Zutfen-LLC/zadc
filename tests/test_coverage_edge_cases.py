"""Additional tests to achieve 100% line and branch coverage.

These cover edge cases in the type validators, canonical serializer,
digest functions, and model helpers that are exercised by error paths
and internal branches.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timezone
from uuid import uuid4

import pytest

from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    canonical_json_bytes,
    canonical_json_text,
    compute_content_digest,
    seal_artifact,
    verify_content_digest,
)
from zadc.canonical import CanonicalJSONTypeError, _normalize_datetime
from zadc.types import (
    validate_git_sha,
    validate_sha256_digest,
    validate_stable_id,
)


class TestTypeValidatorTypeErrorPaths:
    """Cover the TypeError branches in the validator functions."""

    def test_validate_stable_id_rejects_non_string(self) -> None:
        with pytest.raises(TypeError, match="must be a string"):
            validate_stable_id(123)  # type: ignore[arg-type]

    def test_validate_sha256_digest_rejects_non_string(self) -> None:
        with pytest.raises(TypeError, match="must be a string"):
            validate_sha256_digest(123)  # type: ignore[arg-type]

    def test_validate_git_sha_rejects_non_string(self) -> None:
        with pytest.raises(TypeError, match="must be a string"):
            validate_git_sha(123)  # type: ignore[arg-type]


class TestCanonicalBoolNarrowing:
    """Cover the redundant bool branch in _normalize_value."""

    def test_bool_true_normalized(self) -> None:
        # bool is checked before int — this path exercises the redundant bool check
        assert canonical_json_text(True) == "true"

    def test_bool_false_normalized(self) -> None:
        assert canonical_json_text(False) == "false"


class TestCanonicalDateRejection:
    """Cover bare date rejection and UUID rejection."""

    def test_bare_date_rejected(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="date"):
            canonical_json_text(date(2026, 7, 31))

    def test_uuid_rejected(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="UUID"):
            canonical_json_text(uuid4())


class TestCanonicalNaiveDatetime:
    """Cover timezone-naive datetime rejection in canonical serializer."""

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone-naive"):
            canonical_json_text({"ts": datetime(2026, 7, 31, 12, 0, 0)})

    def test_normalize_datetime_naive_directly(self) -> None:
        with pytest.raises(ValueError, match="timezone-naive"):
            _normalize_datetime(datetime(2026, 7, 31, 12, 0, 0))

    def test_normalize_datetime_utc_success(self) -> None:
        """Cover the success path of _normalize_datetime with UTC datetime."""
        result = _normalize_datetime(datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC))
        assert result == "2026-07-31T12:00:00Z"

    def test_normalize_datetime_offset_success(self) -> None:
        """Cover the success path with a non-UTC offset that normalizes to UTC."""
        from datetime import timedelta

        result = _normalize_datetime(
            datetime(2026, 7, 31, 14, 0, 0, tzinfo=timezone(timedelta(hours=2)))
        )
        assert result == "2026-07-31T12:00:00Z"

    def test_datetime_in_canonical_text(self) -> None:
        """A timezone-aware datetime in a dict is properly normalized."""
        result = canonical_json_text({"ts": datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)})
        assert "2026-07-31T12:00:00Z" in result


class TestVerifyRepairParameter:
    """Cover the repair=True error in verify_content_digest."""

    def test_repair_true_raises(self) -> None:
        from datetime import datetime

        env = ArtifactEnvelope(
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000400",
            created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
            producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:t"),
            project_id="zutfen:project:zadc",
            slice_id="RPR-001",
            slice_instance_id="RPR-001A",
            policy=PolicyReference(
                policy_id="zutfen:zadc-policy:standard@0.1.0",
                policy_source_sha="a" * 40,
                policy_digest="sha256:" + "b" * 64,
            ),
            provenance=Provenance(parent_artifact_ids=[]),
        )
        with pytest.raises(ValueError, match="repair"):
            verify_content_digest(env, repair=True)


class TestProvenanceWithDigest:
    """Cover the provenance dict with content_digest branch in digests."""

    def test_envelope_to_digest_input_with_existing_digest(self) -> None:
        """The _envelope_to_digest_input handles a provenance dict with content_digest."""
        from datetime import datetime

        env = ArtifactEnvelope(
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000401",
            created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
            producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:t"),
            project_id="zutfen:project:zadc",
            slice_id="DIG-002",
            slice_instance_id="DIG-002A",
            policy=PolicyReference(
                policy_id="zutfen:zadc-policy:standard@0.1.0",
                policy_source_sha="a" * 40,
                policy_digest="sha256:" + "b" * 64,
            ),
            provenance=Provenance(parent_artifact_ids=[]),
        )
        # Seal then compute — exercises the provenance.content_digest dict path
        sealed = seal_artifact(env)
        digest = compute_content_digest(sealed)
        assert digest is not None


class TestModelDumpJsonCompatible:
    """Cover the model_dump_json_compatible method."""

    def test_model_dump_json_compatible(self) -> None:
        from datetime import datetime

        env = ArtifactEnvelope(
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000402",
            created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
            producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:t"),
            project_id="zutfen:project:zadc",
            slice_id="DMP-001",
            slice_instance_id="DMP-001A",
            policy=PolicyReference(
                policy_id="zutfen:zadc-policy:standard@0.1.0",
                policy_source_sha="a" * 40,
                policy_digest="sha256:" + "b" * 64,
            ),
            provenance=Provenance(parent_artifact_ids=[]),
        )
        result = env.model_dump_json_compatible()
        assert isinstance(result, dict)
        assert "schema" in result
        assert result["schema"] == "https://schemas.zutfen.com/zadc/0.1/artifact.schema.json"


class TestCanonicalJSONTextVsBytes:
    """Cover both canonical_json_text and canonical_json_bytes consistently."""

    def test_text_and_bytes_consistent(self) -> None:
        data = {"b": 1, "a": "hello"}
        text = canonical_json_text(data)
        byts = canonical_json_bytes(data)
        assert text.encode("utf-8") == byts


class TestErrorsExhaustive:
    """Cover all error class functionality."""

    def test_digest_mismatch_error_attributes(self) -> None:
        from zadc.errors import DigestMismatchError

        err = DigestMismatchError(stored="sha256:aaa", expected="sha256:bbb")
        assert err.stored == "sha256:aaa"
        assert err.expected == "sha256:bbb"
        assert "sha256:aaa" in str(err)
        assert "sha256:bbb" in str(err)

    def test_digest_missing_error_message(self) -> None:
        from zadc.errors import DigestMissingError

        err = DigestMissingError("test message")
        assert "test message" in str(err)

    def test_digest_error_is_base_class(self) -> None:
        from zadc.errors import DigestError, DigestMismatchError, DigestMissingError

        assert issubclass(DigestMissingError, DigestError)
        assert issubclass(DigestMismatchError, DigestError)
