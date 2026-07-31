"""A1-BP-001: Envelope validation — valid parse, malformed fail."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from zadc import ArtifactEnvelope, PolicyReference, ProducerIdentity, Provenance


class TestValidEnvelopes:
    """Valid envelopes parse successfully."""

    def test_minimal_envelope(self, sample_envelope: ArtifactEnvelope) -> None:
        assert sample_envelope.artifact_type == "packet"
        assert sample_envelope.contract_version == "0.1.0"

    def test_all_artifact_types(self, sample_envelope: ArtifactEnvelope) -> None:
        for atype in [
            "packet",
            "completion_report",
            "certification_manifest",
            "review_report",
            "decision_record",
            "workflow_bundle",
            "evidence_artifact",
            "observation",
        ]:
            env = sample_envelope.model_copy(update={"artifact_type": atype})
            assert env.artifact_type == atype

    def test_all_actor_types(self, sample_producer: ProducerIdentity) -> None:
        for atype in ["human", "agent", "ci", "validator", "service"]:
            p = sample_producer.model_copy(update={"actor_type": atype})
            assert p.actor_type == atype

    def test_producer_with_optional_fields(self, sample_producer_full: ProducerIdentity) -> None:
        assert sample_producer_full.run_id is not None
        assert sample_producer_full.model == "glm-5.2"
        assert sample_producer_full.provider == "zai"


class TestUnknownFieldsRejected:
    """Unknown fields are rejected (extra=forbid)."""

    def test_envelope_extra_field(self, sample_envelope: ArtifactEnvelope) -> None:
        data = sample_envelope.model_dump(by_alias=True)
        data["unknown_field"] = "evil"
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)

    def test_producer_extra_field(self, sample_producer: ProducerIdentity) -> None:
        data = sample_producer.model_dump()
        data["secret_key"] = "leaked"
        with pytest.raises(ValidationError):
            ProducerIdentity.model_validate(data)

    def test_policy_extra_field(self, sample_policy: PolicyReference) -> None:
        data = sample_policy.model_dump()
        data["extra"] = True
        with pytest.raises(ValidationError):
            PolicyReference.model_validate(data)

    def test_provenance_extra_field(self, sample_provenance_empty: Provenance) -> None:
        data = sample_provenance_empty.model_dump()
        data["unexpected"] = 42
        with pytest.raises(ValidationError):
            Provenance.model_validate(data)


class TestNaiveTimestamps:
    """Naive (timezone-unaware) timestamps fail."""

    def test_naive_created_at(self, sample_envelope: ArtifactEnvelope) -> None:
        data = sample_envelope.model_dump(by_alias=True)
        data["created_at"] = datetime(2026, 7, 31, 12, 0, 0)
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)


class TestMalformedIds:
    """Malformed stable IDs fail."""

    @pytest.mark.parametrize(
        "bad_id",
        [
            "",  # empty
            "   ",  # whitespace-only
            " leading",  # leading whitespace
            "trailing ",  # trailing whitespace
            "has\x00null",  # control character (NUL)
            "has\x07bell",  # control character (BEL)
            "has\nnewline",  # control character (LF)
        ],
    )
    def test_bad_artifact_id(self, sample_envelope: ArtifactEnvelope, bad_id: str) -> None:
        data = sample_envelope.model_dump(by_alias=True)
        data["artifact_id"] = bad_id
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)

    def test_bad_project_id(self, sample_envelope: ArtifactEnvelope) -> None:
        data = sample_envelope.model_dump(by_alias=True)
        data["project_id"] = ""
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)

    def test_bad_actor_id(self, sample_producer: ProducerIdentity) -> None:
        data = sample_producer.model_dump()
        data["actor_id"] = "  "
        with pytest.raises(ValidationError):
            ProducerIdentity.model_validate(data)

    def test_bad_slice_ids(self, sample_envelope: ArtifactEnvelope) -> None:
        for field in ["slice_id", "slice_instance_id"]:
            data = sample_envelope.model_dump(by_alias=True)
            data[field] = "\x00bad"
            with pytest.raises(ValidationError):
                ArtifactEnvelope.model_validate(data)


class TestMalformedDigests:
    """Malformed SHA-256 digests fail."""

    @pytest.mark.parametrize(
        "bad_digest",
        [
            "abc",  # too short
            "sha256:abc",  # too short after prefix
            "sha256:" + "A" * 64,  # uppercase hex
            "sha256:" + "g" * 64,  # non-hex
            "sha256:" + "0" * 63,  # 63 chars
            "sha256:" + "0" * 65,  # 65 chars
            "SHA256:" + "0" * 64,  # uppercase prefix
            "sha256-" + "0" * 64,  # dash instead of colon
            "" + "0" * 64,  # missing prefix
        ],
    )
    def test_bad_policy_digest(self, sample_policy: PolicyReference, bad_digest: str) -> None:
        data = sample_policy.model_dump()
        data["policy_digest"] = bad_digest
        with pytest.raises(ValidationError):
            PolicyReference.model_validate(data)

    def test_bad_content_digest(self, sample_provenance_empty: Provenance) -> None:
        data = sample_provenance_empty.model_dump()
        data["content_digest"] = "sha256:bad"
        with pytest.raises(ValidationError):
            Provenance.model_validate(data)


class TestMalformedGitShas:
    """Malformed Git SHAs fail."""

    @pytest.mark.parametrize(
        "bad_sha",
        [
            "abc",  # too short
            "A" * 40,  # uppercase hex
            "g" * 40,  # non-hex
            "0" * 39,  # 39 chars
            "0" * 41,  # 41 chars
            "",  # empty
        ],
    )
    def test_bad_policy_source_sha(self, sample_policy: PolicyReference, bad_sha: str) -> None:
        data = sample_policy.model_dump()
        data["policy_source_sha"] = bad_sha
        with pytest.raises(ValidationError):
            PolicyReference.model_validate(data)


class TestInvalidEnums:
    """Invalid enum values fail."""

    def test_bad_artifact_type(self, sample_envelope: ArtifactEnvelope) -> None:
        data = sample_envelope.model_dump(by_alias=True)
        data["artifact_type"] = "bogus_type"
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)

    def test_bad_actor_type(self, sample_producer: ProducerIdentity) -> None:
        data = sample_producer.model_dump()
        data["actor_type"] = "robot"
        with pytest.raises(ValidationError):
            ProducerIdentity.model_validate(data)


class TestModelImmutability:
    """Models are frozen (immutable)."""

    def test_envelope_frozen(self, sample_envelope: ArtifactEnvelope) -> None:
        with pytest.raises(ValidationError):
            sample_envelope.artifact_id = "changed"

    def test_producer_frozen(self, sample_producer: ProducerIdentity) -> None:
        with pytest.raises(ValidationError):
            sample_producer.actor_id = "changed"

    def test_provenance_frozen(self, sample_provenance_empty: Provenance) -> None:
        with pytest.raises(ValidationError):
            sample_provenance_empty.parent_artifact_ids = ["x"]


class TestContractVersionImmutable:
    """contract_version must be exactly 0.1.0."""

    def test_wrong_contract_version(self, sample_envelope: ArtifactEnvelope) -> None:
        data = sample_envelope.model_dump(by_alias=True)
        data["contract_version"] = "0.2.0"
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)

    def test_wrong_schema(self, sample_envelope: ArtifactEnvelope) -> None:
        data = sample_envelope.model_dump(by_alias=True)
        data["schema"] = "https://wrong.example/schema.json"
        with pytest.raises(ValidationError):
            ArtifactEnvelope.model_validate(data)
