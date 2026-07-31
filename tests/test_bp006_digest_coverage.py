"""A1-BP-006: Only content_digest is excluded; all other fields are covered;
missing and mismatch are distinct."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from zadc import (
    ArtifactEnvelope,
    DigestMismatchError,
    DigestMissingError,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    compute_content_digest,
    seal_artifact,
    verify_content_digest,
)


def _make_base_envelope() -> ArtifactEnvelope:
    """Build a base envelope for digest tests."""
    return ArtifactEnvelope(
        artifact_type="packet",
        artifact_id="urn:uuid:00000000-0000-0000-0000-000000000100",
        created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
        producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:test"),
        project_id="zutfen:project:zadc",
        slice_id="DIG-001",
        slice_instance_id="DIG-001A",
        policy=PolicyReference(
            policy_id="zutfen:zadc-policy:standard@0.1.0",
            policy_source_sha="a" * 40,
            policy_digest="sha256:" + "b" * 64,
        ),
        provenance=Provenance(parent_artifact_ids=[]),
    )


class TestDigestExclusion:
    """Only content_digest is excluded from digest computation."""

    def test_changing_content_digest_does_not_affect_recomputation(self) -> None:
        """Pre-existing content_digest value does not affect recomputed digest."""
        env_unsealed = _make_base_envelope()
        digest_unsealed = compute_content_digest(env_unsealed)

        # Seal it (sets content_digest)
        env_sealed = seal_artifact(env_unsealed)
        digest_after_seal = compute_content_digest(env_sealed)

        # The recomputed digest must be the same — content_digest is excluded.
        assert digest_unsealed == digest_after_seal

    def test_different_preexisting_digests_same_recomputation(self) -> None:
        """Two envelopes identical except for content_digest have same recomputed digest."""
        env1 = _make_base_envelope()
        env2 = seal_artifact(env1)

        d1 = compute_content_digest(env1)
        d2 = compute_content_digest(env2)
        assert d1 == d2


class TestAllFieldsCovered:
    """All fields except content_digest affect the digest."""

    def test_changing_artifact_id_changes_digest(self) -> None:
        env1 = _make_base_envelope()
        env2 = env1.model_copy(
            update={"artifact_id": "urn:uuid:00000000-0000-0000-0000-000000000200"}
        )
        assert compute_content_digest(env1) != compute_content_digest(env2)

    def test_changing_artifact_type_changes_digest(self) -> None:
        env1 = _make_base_envelope()
        env2 = env1.model_copy(update={"artifact_type": "observation"})
        assert compute_content_digest(env1) != compute_content_digest(env2)

    def test_changing_created_at_changes_digest(self) -> None:
        env1 = _make_base_envelope()
        env2 = env1.model_copy(update={"created_at": datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)})
        assert compute_content_digest(env1) != compute_content_digest(env2)

    def test_changing_producer_changes_digest(self) -> None:
        env1 = _make_base_envelope()
        new_producer = env1.producer.model_copy(update={"actor_id": "zutfen:human:other"})
        env2 = env1.model_copy(update={"producer": new_producer})
        assert compute_content_digest(env1) != compute_content_digest(env2)

    def test_changing_producer_optional_fields_change_digest(self) -> None:
        env1 = _make_base_envelope()
        new_producer = env1.producer.model_copy(update={"model": "gpt-5"})
        env2 = env1.model_copy(update={"producer": new_producer})
        assert compute_content_digest(env1) != compute_content_digest(env2)

    def test_changing_project_id_changes_digest(self) -> None:
        env1 = _make_base_envelope()
        env2 = env1.model_copy(update={"project_id": "zutfen:project:other"})
        assert compute_content_digest(env1) != compute_content_digest(env2)

    def test_changing_slice_id_changes_digest(self) -> None:
        env1 = _make_base_envelope()
        env2 = env1.model_copy(update={"slice_id": "OTHER-001"})
        assert compute_content_digest(env1) != compute_content_digest(env2)

    def test_changing_policy_changes_digest(self) -> None:
        env1 = _make_base_envelope()
        new_policy = env1.policy.model_copy(update={"policy_digest": "sha256:" + "c" * 64})
        env2 = env1.model_copy(update={"policy": new_policy})
        assert compute_content_digest(env1) != compute_content_digest(env2)

    def test_changing_provenance_parents_changes_digest(self) -> None:
        env1 = _make_base_envelope()
        new_provenance = env1.provenance.model_copy(
            update={"parent_artifact_ids": ["urn:uuid:00000000-0000-0000-0000-000000000099"]}
        )
        env2 = env1.model_copy(update={"provenance": new_provenance})
        assert compute_content_digest(env1) != compute_content_digest(env2)


class TestMissingVsMismatch:
    """Missing and mismatch are distinct errors."""

    def test_missing_digest_raises_missing_error(self) -> None:
        """Unsealed envelope (no content_digest) raises DigestMissingError."""
        env = _make_base_envelope()
        assert env.provenance.content_digest is None
        with pytest.raises(DigestMissingError, match="absent"):
            verify_content_digest(env)

    def test_correct_seal_verifies(self) -> None:
        """Properly sealed envelope verifies without error."""
        env = _make_base_envelope()
        sealed = seal_artifact(env)
        result = verify_content_digest(sealed)
        assert result == sealed.provenance.content_digest

    def test_tampered_digest_raises_mismatch_error(self) -> None:
        """Wrong digest raises DigestMismatchError, not DigestMissingError."""
        env = _make_base_envelope()
        sealed = seal_artifact(env)
        # Tamper with the digest
        tampered_provenance = sealed.provenance.model_copy(
            update={"content_digest": "sha256:" + "0" * 64}
        )
        tampered = sealed.model_copy(update={"provenance": tampered_provenance})
        with pytest.raises(DigestMismatchError, match="mismatch"):
            verify_content_digest(tampered)

    def test_mismatch_error_carries_stored_and_expected(self) -> None:
        """DigestMismatchError exposes stored and expected values."""
        env = _make_base_envelope()
        sealed = seal_artifact(env)
        wrong = "sha256:" + "0" * 64
        tampered_provenance = sealed.provenance.model_copy(update={"content_digest": wrong})
        tampered = sealed.model_copy(update={"provenance": tampered_provenance})
        try:
            verify_content_digest(tampered)
            pytest.fail("should have raised")
        except DigestMismatchError as e:
            assert e.stored == wrong
            assert e.expected != wrong

    def test_modified_envelope_raises_mismatch_error(self) -> None:
        """Sealed envelope modified after sealing raises mismatch."""
        env = _make_base_envelope()
        sealed = seal_artifact(env)
        # Modify a field after sealing
        modified = sealed.model_copy(
            update={"artifact_id": "urn:uuid:00000000-0000-0000-0000-000000000999"}
        )
        with pytest.raises(DigestMismatchError):
            verify_content_digest(modified)

    def test_verify_never_repairs(self) -> None:
        """verify_content_digest never repairs a mismatch."""
        env = _make_base_envelope()
        sealed = seal_artifact(env)
        wrong = "sha256:" + "0" * 64
        tampered_provenance = sealed.provenance.model_copy(update={"content_digest": wrong})
        tampered = sealed.model_copy(update={"provenance": tampered_provenance})
        with pytest.raises(DigestMismatchError):
            verify_content_digest(tampered)
        # The input must not have been mutated
        assert tampered.provenance.content_digest == wrong
