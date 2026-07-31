"""FIX1-BP-02: Strict timestamp and scalar input behavior.

Also FIX1-BP-03: Deep immutability.
"""

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    compute_content_digest,
    seal_artifact,
)


def _make_base() -> ArtifactEnvelope:
    return ArtifactEnvelope(
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


class TestStrictTimestampRejection:
    """Reject created_at as int, float, Decimal, bool, bytes, naive datetime, date."""

    def test_reject_int(self) -> None:
        env = _make_base()
        data = env.model_dump(by_alias=True)
        data["created_at"] = 1234567890
        with pytest.raises((ValidationError, TypeError)):
            ArtifactEnvelope.model_validate(data)

    def test_reject_float(self) -> None:
        env = _make_base()
        data = env.model_dump(by_alias=True)
        data["created_at"] = 1234567890.5
        with pytest.raises((ValidationError, TypeError)):
            ArtifactEnvelope.model_validate(data)

    def test_reject_decimal(self) -> None:
        env = _make_base()
        data = env.model_dump(by_alias=True)
        data["created_at"] = Decimal("1234567890.5")
        with pytest.raises((ValidationError, TypeError)):
            ArtifactEnvelope.model_validate(data)

    def test_reject_bool(self) -> None:
        env = _make_base()
        data = env.model_dump(by_alias=True)
        data["created_at"] = True
        with pytest.raises((ValidationError, TypeError)):
            ArtifactEnvelope.model_validate(data)

    def test_reject_bytes(self) -> None:
        env = _make_base()
        data = env.model_dump(by_alias=True)
        data["created_at"] = b"2026-07-31T12:00:00Z"
        with pytest.raises((ValidationError, TypeError)):
            ArtifactEnvelope.model_validate(data)

    def test_reject_naive_datetime(self) -> None:
        env = _make_base()
        data = env.model_dump(by_alias=True)
        data["created_at"] = datetime(2026, 7, 31, 12, 0, 0)
        with pytest.raises((ValidationError, TypeError, ValueError)):
            ArtifactEnvelope.model_validate(data)

    def test_reject_date(self) -> None:
        env = _make_base()
        data = env.model_dump(by_alias=True)
        data["created_at"] = date(2026, 7, 31)
        with pytest.raises((ValidationError, TypeError)):
            ArtifactEnvelope.model_validate(data)


class TestAcceptValidTimestamps:
    """Accept timezone-aware datetime and RFC 3339 strings from decoded JSON."""

    def test_accept_tz_aware_datetime(self) -> None:
        env = _make_base()
        assert env.created_at == datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)

    def test_accept_rfc3339_string_from_json(self) -> None:
        env = _make_base()
        data = env.model_dump(by_alias=True)
        data["created_at"] = "2026-07-31T12:00:00Z"
        env2 = ArtifactEnvelope.model_validate(data)
        assert env2.created_at == datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)


class TestOffsetNormalization:
    """Equivalent offsets produce identical UTC-Z canonical bytes."""

    def test_utc_vs_zero_offset(self) -> None:
        env_utc = _make_base()
        env_off = ArtifactEnvelope(
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
            created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone(timedelta(hours=0))),
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
        assert compute_content_digest(env_utc) == compute_content_digest(env_off)

    def test_positive_offset_normalizes(self) -> None:
        env_utc = _make_base()
        env_pos = ArtifactEnvelope(
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
            created_at=datetime(
                2026, 7, 31, 17, 30, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))
            ),
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
        assert compute_content_digest(env_utc) == compute_content_digest(env_pos)


class TestRejectNonStringScalars:
    """Reject non-string IDs, SHAs, and digests without coercion."""

    def test_reject_int_actor_id(self) -> None:
        with pytest.raises((ValidationError, TypeError)):
            ProducerIdentity(actor_type="human", actor_id=123)  # type: ignore[arg-type]

    def test_reject_int_policy_source_sha(self) -> None:
        with pytest.raises((ValidationError, TypeError)):
            PolicyReference(
                policy_id="zutfen:zadc-policy:standard@0.1.0",
                policy_source_sha=42,  # type: ignore[arg-type]
                policy_digest="sha256:" + "b" * 64,
            )

    def test_reject_int_policy_digest(self) -> None:
        with pytest.raises((ValidationError, TypeError)):
            PolicyReference(
                policy_id="zutfen:zadc-policy:standard@0.1.0",
                policy_source_sha="a" * 40,
                policy_digest=42,  # type: ignore[arg-type]
            )


class TestDeepImmutability:
    """FIX1-BP-03: Deep immutability of provenance and models."""

    def test_parent_artifact_ids_is_tuple(self) -> None:
        prov = Provenance(parent_artifact_ids=("urn:uuid:00000000-0000-0000-0000-000000000098",))
        assert isinstance(prov.parent_artifact_ids, tuple)

    def test_parent_ids_immutable(self) -> None:
        prov = Provenance(parent_artifact_ids=("urn:uuid:00000000-0000-0000-0000-000000000098",))
        with pytest.raises(AttributeError):
            prov.parent_artifact_ids.append("x")  # type: ignore[attr-defined]

    def test_source_list_mutation_after_construction(self) -> None:
        """Mutating the source list does not affect the model."""
        source: list[str] = ["urn:uuid:00000000-0000-0000-0000-000000000098"]
        prov = Provenance(parent_artifact_ids=tuple(source))
        source.append("urn:uuid:00000000-0000-0000-0000-000000000099")
        assert len(prov.parent_artifact_ids) == 1

    def test_sealed_input_unchanged_by_compute(self) -> None:
        env = _make_base()
        sealed = seal_artifact(env)
        # Unsealed input must still have None digest
        assert env.provenance.content_digest is None
        # Sealed must have a digest
        assert sealed.provenance.content_digest is not None

    def test_seal_does_not_mutate_parents(self) -> None:
        env = _make_base()
        original_ids = env.provenance.parent_artifact_ids
        sealed = seal_artifact(env)
        assert env.provenance.parent_artifact_ids == original_ids
        assert sealed.provenance.parent_artifact_ids == original_ids

    def test_envelope_attribute_assignment_fails(self) -> None:
        env = _make_base()
        with pytest.raises((ValidationError, TypeError)):
            env.artifact_id = "changed"

    def test_nested_producer_assignment_fails(self) -> None:
        env = _make_base()
        with pytest.raises((ValidationError, TypeError)):
            env.producer.actor_id = "changed"

    def test_sealing_uses_validated_reconstruction(self) -> None:
        """Sealing produces a model that passes validation independently."""
        env = _make_base()
        sealed = seal_artifact(env)
        # The sealed model should be re-creatable from its own dump
        data = sealed.model_dump(by_alias=True)
        reloaded = ArtifactEnvelope.model_validate(data)
        assert reloaded == sealed
