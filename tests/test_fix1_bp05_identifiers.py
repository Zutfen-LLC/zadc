"""FIX1-BP-05: Global URI IDs and slice IDs.

Tests GlobalId (URI-shaped) and SliceId (human-friendly grammar).
"""

import pytest
from pydantic import ValidationError

from zadc import ArtifactEnvelope, PolicyReference, ProducerIdentity, Provenance
from zadc.types import validate_global_id, validate_slice_id


class TestGlobalIdAcceptance:
    """Accept representative URI schemes."""

    @pytest.mark.parametrize(
        "value",
        [
            "urn:uuid:00000000-0000-0000-0000-000000000001",
            "zutfen:human:eric",
            "github:Zutfen-LLC/zadc",
            "zutfen:project:zadc",
            "https://example.com/artifact/001",
        ],
    )
    def test_accept_valid_global_ids(self, value: str) -> None:
        assert validate_global_id(value) == value

    def test_accept_in_model_producer(self) -> None:
        prod = ProducerIdentity(
            actor_type="human", actor_id="urn:uuid:00000000-0000-0000-0000-0000000000aa"
        )
        assert prod.actor_id == "urn:uuid:00000000-0000-0000-0000-0000000000aa"


class TestGlobalIdRejection:
    """Reject invalid global IDs."""

    @pytest.mark.parametrize(
        "bad_value",
        [
            "plain-identifier",  # no scheme
            "   ",  # whitespace-only
            ":noscheme",  # empty scheme
            "1bad:scheme",  # scheme starts with digit
            "urn:uuid:ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ",  # uppercase hex in uuid
            "urn:uuid:not-a-uuid",
            " leading:scheme",
            "trailing:scheme ",
        ],
    )
    def test_reject_invalid_global_ids(self, bad_value: str) -> None:
        with pytest.raises((ValueError, TypeError)):
            validate_global_id(bad_value)

    def test_reject_unicode_control(self) -> None:
        with pytest.raises(ValueError, match="Unicode category"):
            validate_global_id("zutfen:\x00null")

    def test_reject_unicode_format(self) -> None:
        with pytest.raises(ValueError, match="Unicode category"):
            validate_global_id("zutfen:\u200bzerowidth")

    def test_reject_unicode_surrogate(self) -> None:
        with pytest.raises(ValueError, match="Unicode category"):
            validate_global_id("zutfen:\ud800surrogate")

    def test_reject_non_string(self) -> None:
        with pytest.raises(TypeError):
            validate_global_id(123)  # type: ignore[arg-type]


class TestSliceIdAcceptance:
    """Accept representative slice IDs."""

    @pytest.mark.parametrize(
        "value",
        [
            "ZADC-001A1",
            "ENG-PORTAL-RECEIPTS-001A-FIX1",
            "ZADC-001A",
            "X",
            "A1",
        ],
    )
    def test_accept_valid_slice_ids(self, value: str) -> None:
        assert validate_slice_id(value) == value

    def test_accept_in_model_envelope(self) -> None:
        from datetime import UTC, datetime

        env = ArtifactEnvelope(
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
            created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
            producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:eric"),
            project_id="zutfen:project:zadc",
            slice_id="ENG-PORTAL-001A-FIX1",
            slice_instance_id="ENG-PORTAL-001A-FIX1-A",
            policy=PolicyReference(
                policy_id="zutfen:zadc-policy:standard@0.1.0",
                policy_source_sha="a" * 40,
                policy_digest="sha256:" + "b" * 64,
            ),
            provenance=Provenance(parent_artifact_ids=()),
        )
        assert env.slice_id == "ENG-PORTAL-001A-FIX1"


class TestSliceIdRejection:
    """Reject unsafe or blank slice IDs."""

    @pytest.mark.parametrize(
        "bad_value",
        [
            "",  # empty
            "   ",  # whitespace-only
            "lowercase",  # lowercase
            "with space",  # space
            "-leading-hyphen",  # starts with hyphen
            "trailing-hyphen-",  # ends with hyphen
            "path/injection",  # path separator
            "ctrl\x00char",  # control char
            "format\u200bchar",  # format char
            "unicode\u4e00char",  # non-ASCII (CJK)
        ],
    )
    def test_reject_invalid_slice_ids(self, bad_value: str) -> None:
        with pytest.raises((ValueError, TypeError)):
            validate_slice_id(bad_value)

    def test_reject_non_string(self) -> None:
        with pytest.raises(TypeError):
            validate_slice_id(42)  # type: ignore[arg-type]

    def test_reject_in_model(self) -> None:
        from datetime import UTC, datetime

        with pytest.raises(ValidationError):
            ArtifactEnvelope(
                artifact_type="packet",
                artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
                created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
                producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:eric"),
                project_id="zutfen:project:zadc",
                slice_id="lowercase-invalid",
                slice_instance_id="ZADC-001A1",
                policy=PolicyReference(
                    policy_id="zutfen:zadc-policy:standard@0.1.0",
                    policy_source_sha="a" * 40,
                    policy_digest="sha256:" + "b" * 64,
                ),
                provenance=Provenance(parent_artifact_ids=()),
            )
