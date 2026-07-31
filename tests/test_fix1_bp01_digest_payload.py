"""FIX1-BP-01: Digest member is absent from exact digest payload.

Also FIX1-BP-08: golden vectors updated to the corrected digest exclusion
semantics.
"""

from datetime import UTC, datetime

import pytest

from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    compute_content_digest,
    seal_artifact,
    verify_content_digest,
)
from zadc.digests import get_digest_input_bytes
from zadc.types import CONTRACT_VERSION, SCHEMA_ID


def _make_envelope() -> ArtifactEnvelope:
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


class TestDigestPayloadExcludesContentDigest:
    """FIX1-A: content_digest key is absent from digest payload."""

    def test_content_digest_key_absent_from_payload(self) -> None:
        """The substring 'content_digest' must not appear in the digest payload."""
        env = _make_envelope()
        raw = get_digest_input_bytes(env)
        assert b"content_digest" not in raw

    def test_exact_digest_payload_bytes(self) -> None:
        """Assert exact canonical digest-input bytes for a representative envelope."""
        env = _make_envelope()
        raw = get_digest_input_bytes(env)
        # Fixed expected value computed from the exact payload above
        expected = (
            b'{"artifact_id":"urn:uuid:00000000-0000-0000-0000-000000000001",'
            b'"artifact_type":"packet",'
            b'"contract_version":"0.1.0",'
            b'"created_at":"2026-07-31T12:00:00Z",'
            b'"policy":{"policy_digest":"sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",'
            b'"policy_id":"zutfen:zadc-policy:standard@0.1.0",'
            b'"policy_source_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},'
            b'"producer":{"actor_id":"zutfen:human:eric","actor_type":"human",'
            b'"model":null,"provider":null,"run_id":null},'
            b'"project_id":"zutfen:project:zadc",'
            b'"provenance":{"parent_artifact_ids":[]},'
            b'"schema":"https://schemas.zutfen.com/zadc/0.1/artifact.schema.json",'
            b'"slice_id":"ZADC-001A",'
            b'"slice_instance_id":"ZADC-001A1"}'
        )
        assert raw == expected

    def test_expected_digest_value(self) -> None:
        """Fixed expected digest computed independently of test-under-test logic."""
        env = _make_envelope()
        digest = compute_content_digest(env)
        # This value is fixed and was computed once from the exact payload above.
        assert digest == "sha256:99676878dd6383eb924022e02b2f6e9f20d479e3ae304ad834fda444632e3e60"


class TestDigestUnchangedByStoredDigest:
    """Replacing or removing a stored digest does not change recomputed digest."""

    def test_unsealed_and_sealed_same_digest(self) -> None:
        env = _make_envelope()
        d_unsealed = compute_content_digest(env)
        sealed = seal_artifact(env)
        d_sealed = compute_content_digest(sealed)
        assert d_unsealed == d_sealed

    def test_different_stored_digests_same_recomputation(self) -> None:
        env = _make_envelope()
        sealed = seal_artifact(env)
        d1 = compute_content_digest(sealed)
        d2 = compute_content_digest(env)
        assert d1 == d2


class TestOtherFieldsAffectDigest:
    """Changing any other envelope field changes the digest."""

    def test_changing_artifact_id(self) -> None:
        env = _make_envelope()
        data = env.model_dump(by_alias=True)
        data["artifact_id"] = "urn:uuid:00000000-0000-0000-0000-000000000099"
        env2 = ArtifactEnvelope.model_validate(data)
        assert compute_content_digest(env) != compute_content_digest(env2)

    def test_changing_artifact_type(self) -> None:
        env = _make_envelope()
        data = env.model_dump(by_alias=True)
        data["artifact_type"] = "observation"
        env2 = ArtifactEnvelope.model_validate(data)
        assert compute_content_digest(env) != compute_content_digest(env2)

    def test_changing_created_at(self) -> None:
        env = _make_envelope()
        data = env.model_dump(by_alias=True)
        data["created_at"] = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC).isoformat()
        env2 = ArtifactEnvelope.model_validate(data)
        assert compute_content_digest(env) != compute_content_digest(env2)

    def test_changing_producer_actor_id(self) -> None:
        env = _make_envelope()
        data = env.model_dump(by_alias=True)
        data["producer"]["actor_id"] = "zutfen:human:other"
        env2 = ArtifactEnvelope.model_validate(data)
        assert compute_content_digest(env) != compute_content_digest(env2)

    def test_changing_project_id(self) -> None:
        env = _make_envelope()
        data = env.model_dump(by_alias=True)
        data["project_id"] = "zutfen:project:other"
        env2 = ArtifactEnvelope.model_validate(data)
        assert compute_content_digest(env) != compute_content_digest(env2)

    def test_changing_slice_id(self) -> None:
        env = _make_envelope()
        data = env.model_dump(by_alias=True)
        data["slice_id"] = "ZADC-002B"
        env2 = ArtifactEnvelope.model_validate(data)
        assert compute_content_digest(env) != compute_content_digest(env2)

    def test_changing_policy_digest(self) -> None:
        env = _make_envelope()
        data = env.model_dump(by_alias=True)
        data["policy"]["policy_digest"] = "sha256:" + "c" * 64
        env2 = ArtifactEnvelope.model_validate(data)
        assert compute_content_digest(env) != compute_content_digest(env2)

    def test_changing_provenance_parents(self) -> None:
        env = _make_envelope()
        data = env.model_dump(by_alias=True)
        data["provenance"]["parent_artifact_ids"] = [
            "urn:uuid:00000000-0000-0000-0000-000000000098"
        ]
        env2 = ArtifactEnvelope.model_validate(data)
        assert compute_content_digest(env) != compute_content_digest(env2)

    def test_changing_producer_model(self) -> None:
        env = _make_envelope()
        data = env.model_dump(by_alias=True)
        data["producer"]["model"] = "gpt-5"
        env2 = ArtifactEnvelope.model_validate(data)
        assert compute_content_digest(env) != compute_content_digest(env2)


class TestDigestMissingVsMismatch:
    """Missing and mismatch are distinct errors."""

    def test_missing_digest_raises_missing(self, sample_envelope: ArtifactEnvelope) -> None:
        from zadc import DigestMissingError

        with pytest.raises(DigestMissingError):
            verify_content_digest(sample_envelope)

    def test_correct_seal_verifies(self) -> None:
        env = _make_envelope()
        sealed = seal_artifact(env)
        result = verify_content_digest(sealed)
        assert result == sealed.provenance.content_digest

    def test_tampered_digest_raises_mismatch(self) -> None:
        from zadc import DigestMismatchError

        env = _make_envelope()
        sealed = seal_artifact(env)
        data = sealed.model_dump(by_alias=True)
        data["provenance"]["content_digest"] = "sha256:" + "0" * 64
        tampered = ArtifactEnvelope.model_validate(data)
        with pytest.raises(DigestMismatchError):
            verify_content_digest(tampered)
