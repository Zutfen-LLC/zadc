"""Coverage edge cases for type validators, canonical serializer,
digests, and model helpers."""

from datetime import UTC, date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    canonical_json_bytes,
    canonical_json_text,
    seal_artifact,
    verify_content_digest,
)
from zadc.canonical import CanonicalJSONTypeError, _normalize_datetime, _normalize_value
from zadc.types import (
    CONTRACT_VERSION,
    SCHEMA_ID,
    validate_git_sha,
    validate_global_id,
    validate_sha256_digest,
    validate_slice_id,
)


def _make_env() -> ArtifactEnvelope:
    return ArtifactEnvelope(
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


# -- Type validators: TypeError paths --


class TestTypeValidatorTypeErrors:
    def test_global_id_non_string(self) -> None:
        with pytest.raises(TypeError):
            validate_global_id(123)  # type: ignore[arg-type]

    def test_slice_id_non_string(self) -> None:
        with pytest.raises(TypeError):
            validate_slice_id(123)  # type: ignore[arg-type]

    def test_sha256_non_string(self) -> None:
        with pytest.raises(TypeError):
            validate_sha256_digest(123)  # type: ignore[arg-type]

    def test_git_sha_non_string(self) -> None:
        with pytest.raises(TypeError):
            validate_git_sha(123)  # type: ignore[arg-type]


# -- Type validators: rejection edge cases --


class TestTypeValidatorRejections:
    def test_global_id_whitespace(self) -> None:
        with pytest.raises(ValueError):
            validate_global_id(" urn:uuid:x")

    def test_global_id_invalid_scheme(self) -> None:
        with pytest.raises(ValueError, match="scheme"):
            validate_global_id("1bad:x")

    def test_global_id_empty(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_global_id("")

    def test_global_id_uppercase_uuid(self) -> None:
        with pytest.raises(ValueError, match="lowercase"):
            validate_global_id("urn:uuid:ABCDEF00-0000-0000-0000-000000000000")

    def test_global_id_invalid_uuid(self) -> None:
        with pytest.raises(ValueError, match="urn:uuid"):
            validate_global_id("urn:uuid:not-a-uuid-value")

    def test_slice_id_leading_hyphen(self) -> None:
        with pytest.raises(ValueError, match="slice"):
            validate_slice_id("-BAD")

    def test_slice_id_empty(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_slice_id("")

    def test_sha256_bad(self) -> None:
        with pytest.raises(ValueError):
            validate_sha256_digest("sha256:bad")

    def test_git_sha_bad(self) -> None:
        with pytest.raises(ValueError):
            validate_git_sha("tooshort")


# -- Canonical serializer edge cases --


class TestCanonicalEdgeCases:
    def test_normalize_value_decimal(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="Decimal"):
            _normalize_value(Decimal("1.5"))

    def test_normalize_value_bytes(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="bytes"):
            _normalize_value(b"hello")

    def test_normalize_value_bytearray(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="bytearray"):
            _normalize_value(bytearray(b"hello"))

    def test_normalize_value_set(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="set"):
            _normalize_value({1, 2})

    def test_normalize_value_date(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="date"):
            _normalize_value(date(2026, 7, 31))

    def test_normalize_value_uuid(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="UUID"):
            _normalize_value(uuid4())

    def test_normalize_value_tuple(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="tuple"):
            _normalize_value((1, 2))

    def test_normalize_value_non_string_key(self) -> None:
        with pytest.raises(CanonicalJSONTypeError, match="non-string"):
            _normalize_value({1: "v"})

    def test_normalize_value_arbitrary_object(self) -> None:
        class Custom:
            pass

        with pytest.raises(CanonicalJSONTypeError):
            _normalize_value(Custom())

    def test_normalize_datetime_naive(self) -> None:
        with pytest.raises(ValueError, match="timezone-naive"):
            _normalize_datetime(datetime(2026, 7, 31, 12, 0, 0))

    def test_normalize_datetime_utc(self) -> None:
        result = _normalize_datetime(datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC))
        assert result == "2026-07-31T12:00:00Z"

    def test_normalize_datetime_offset(self) -> None:
        from datetime import timedelta

        result = _normalize_datetime(
            datetime(2026, 7, 31, 14, 0, 0, tzinfo=timezone(timedelta(hours=2)))
        )
        assert result == "2026-07-31T12:00:00Z"

    def test_canonical_text_datetime_in_dict(self) -> None:
        result = canonical_json_text({"ts": datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)})
        assert "2026-07-31T12:00:00Z" in result

    def test_canonical_text_and_bytes_consistent(self) -> None:
        data: dict[str, Any] = {"b": 1, "a": 2}
        text = canonical_json_text(data)
        byts = canonical_json_bytes(data)
        assert text.encode("utf-8") == byts

    def test_canonical_bool_true(self) -> None:
        assert canonical_json_text(True) == "true"

    def test_canonical_bool_false(self) -> None:
        assert canonical_json_text(False) == "false"

    def test_canonical_none(self) -> None:
        assert canonical_json_text(None) == "null"

    def test_canonical_int(self) -> None:
        assert canonical_json_text(42) == "42"


# -- Digests edge cases --


class TestDigestEdgeCases:
    def test_verify_repair_raises(self) -> None:
        env = _make_env()
        with pytest.raises(ValueError, match="repair"):
            verify_content_digest(env, repair=True)

    def test_digest_with_parents(self) -> None:
        env = ArtifactEnvelope(
            schema=SCHEMA_ID,
            contract_version=CONTRACT_VERSION,
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000003",
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
            provenance=Provenance(
                parent_artifact_ids=("urn:uuid:00000000-0000-0000-0000-000000000098",)
            ),
        )
        sealed = seal_artifact(env)
        verify_content_digest(sealed)


# -- Model edge cases --


class TestModelEdgeCases:
    def test_created_at_from_rfc3339_string(self) -> None:
        env = ArtifactEnvelope(
            schema=SCHEMA_ID,
            contract_version=CONTRACT_VERSION,
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000004",
            created_at="2026-07-31T12:00:00Z",  # type: ignore[arg-type]
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
        assert env.created_at == datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)

    def test_created_at_from_offset_string(self) -> None:
        env = ArtifactEnvelope(
            schema=SCHEMA_ID,
            contract_version=CONTRACT_VERSION,
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000005",
            created_at="2026-07-31T14:00:00+02:00",  # type: ignore[arg-type]
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
        assert env.created_at == datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)

    def test_created_at_naive_string_rejected(self) -> None:
        with pytest.raises((ValidationError, ValueError)):
            ArtifactEnvelope(
                schema=SCHEMA_ID,
                contract_version=CONTRACT_VERSION,
                artifact_type="packet",
                artifact_id="urn:uuid:00000000-0000-0000-0000-000000000006",
                created_at="2026-07-31T12:00:00",  # type: ignore[arg-type]
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

    def test_created_at_bad_string_rejected(self) -> None:
        with pytest.raises((ValidationError, ValueError)):
            ArtifactEnvelope(
                schema=SCHEMA_ID,
                contract_version=CONTRACT_VERSION,
                artifact_type="packet",
                artifact_id="urn:uuid:00000000-0000-0000-0000-000000000007",
                created_at="not-a-date",  # type: ignore[arg-type]
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

    def test_provenance_accepts_tuple(self) -> None:
        prov = Provenance(parent_artifact_ids=("urn:uuid:00000000-0000-0000-0000-000000000098",))
        assert isinstance(prov.parent_artifact_ids, tuple)
        assert len(prov.parent_artifact_ids) == 1


# -- Error class coverage --


class TestErrorClasses:
    def test_wrong_contract_version(self) -> None:
        env = _make_env()
        data = env.model_dump(by_alias=True)
        data["contract_version"] = "0.2.0"
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)

    def test_wrong_schema(self) -> None:
        env = _make_env()
        data = env.model_dump(by_alias=True)
        data["schema"] = "https://wrong.example/schema.json"
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)

    def test_digest_mismatch_attributes(self) -> None:
        from zadc.errors import DigestMismatchError

        err = DigestMismatchError(stored="sha256:aaa", expected="sha256:bbb")
        assert err.stored == "sha256:aaa"
        assert err.expected == "sha256:bbb"
        assert "sha256:aaa" in str(err)
        assert "sha256:bbb" in str(err)

    def test_digest_missing_message(self) -> None:
        from zadc.errors import DigestMissingError

        err = DigestMissingError("test message")
        assert "test message" in str(err)

    def test_digest_error_hierarchy(self) -> None:
        from zadc.errors import DigestError, DigestMismatchError, DigestMissingError

        assert issubclass(DigestMissingError, DigestError)
        assert issubclass(DigestMismatchError, DigestError)
