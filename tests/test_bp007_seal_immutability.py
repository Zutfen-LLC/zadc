"""A1-BP-007: Models are immutable; seal returns a new instance and is
idempotent; sealed serialization includes digest."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    compute_content_digest,
    seal_artifact,
    verify_content_digest,
)


def _make_envelope() -> ArtifactEnvelope:
    return ArtifactEnvelope(
        artifact_type="packet",
        artifact_id="urn:uuid:00000000-0000-0000-0000-000000000200",
        created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
        producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:test"),
        project_id="zutfen:project:zadc",
        slice_id="SEAL-001",
        slice_instance_id="SEAL-001A",
        policy=PolicyReference(
            policy_id="zutfen:zadc-policy:standard@0.1.0",
            policy_source_sha="a" * 40,
            policy_digest="sha256:" + "b" * 64,
        ),
        provenance=Provenance(parent_artifact_ids=[]),
    )


class TestImmutability:
    """Models are immutable (frozen=True)."""

    def test_envelope_assignment_fails(self) -> None:
        env = _make_envelope()
        with pytest.raises((ValidationError, TypeError)):
            env.artifact_id = "changed"

    def test_producer_assignment_fails(self) -> None:
        env = _make_envelope()
        with pytest.raises((ValidationError, TypeError)):
            env.producer.actor_id = "changed"


class TestSealReturnsNewInstance:
    """seal_artifact returns a new immutable instance."""

    def test_seal_returns_new_object(self) -> None:
        env = _make_envelope()
        sealed = seal_artifact(env)
        assert sealed is not env

    def test_seal_does_not_mutate_input(self) -> None:
        """The input envelope is never mutated by seal_artifact."""
        env = _make_envelope()
        original_digest = env.provenance.content_digest
        sealed = seal_artifact(env)
        # Input must still have None digest
        assert env.provenance.content_digest == original_digest
        assert env.provenance.content_digest is None
        # Sealed copy must have the digest
        assert sealed.provenance.content_digest is not None

    def test_seal_returns_different_provenance_object(self) -> None:
        env = _make_envelope()
        sealed = seal_artifact(env)
        assert sealed.provenance is not env.provenance


class TestSealIdempotence:
    """Sealing is idempotent — re-sealing an unmodified sealed envelope produces the same digest."""

    def test_double_seal_same_digest(self) -> None:
        env = _make_envelope()
        sealed1 = seal_artifact(env)
        sealed2 = seal_artifact(sealed1)
        assert sealed1.provenance.content_digest == sealed2.provenance.content_digest

    def test_compute_digest_same_before_and_after_seal(self) -> None:
        env = _make_envelope()
        d_before = compute_content_digest(env)
        sealed = seal_artifact(env)
        d_after = compute_content_digest(sealed)
        assert d_before == d_after
        assert sealed.provenance.content_digest == d_before

    def test_seal_idempotent_chain(self) -> None:
        """Chaining seal operations yields identical digests."""
        env = _make_envelope()
        digests = []
        current = env
        for _ in range(5):
            current = seal_artifact(current)
            digests.append(current.provenance.content_digest)
        assert len(set(digests)) == 1


class TestSealedSerializationIncludesDigest:
    """Sealed serialization includes the content_digest."""

    def test_unsealed_serialization_omits_digest_value(self) -> None:
        env = _make_envelope()
        data = env.model_dump(mode="json", by_alias=True)
        assert data["provenance"]["content_digest"] is None

    def test_sealed_serialization_includes_digest(self) -> None:
        env = _make_envelope()
        sealed = seal_artifact(env)
        data = sealed.model_dump(mode="json", by_alias=True)
        assert data["provenance"]["content_digest"] is not None
        assert data["provenance"]["content_digest"].startswith("sha256:")

    def test_sealed_envelope_verifies(self) -> None:
        env = _make_envelope()
        sealed = seal_artifact(env)
        verify_content_digest(sealed)  # should not raise


class TestRoundTripSealReloadVerify:
    """Construct -> seal -> serialize -> reload -> verify round-trip."""

    def test_construct_seal_serialize_reload_verify(self) -> None:
        # 1. Construct
        env = _make_envelope()
        # 2. Seal
        sealed = seal_artifact(env)
        # 3. Serialize
        data = sealed.model_dump(mode="json", by_alias=True)
        import json

        json_str = json.dumps(data, sort_keys=True)
        # 4. Reload (simulate from JSON)
        reloaded_data = json.loads(json_str)
        reloaded = ArtifactEnvelope.model_validate(reloaded_data)
        # 5. Verify
        verify_content_digest(reloaded)  # should not raise
        assert reloaded.provenance.content_digest == sealed.provenance.content_digest
