"""A1-BP-002: Equivalent timestamp offsets produce identical canonical bytes/digests;
uppercase Z and deterministic fractional seconds."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    canonical_json_bytes,
    compute_content_digest,
)


def _make_envelope(created_at: datetime) -> ArtifactEnvelope:
    """Build a minimal envelope with the given created_at."""
    return ArtifactEnvelope(
        artifact_type="packet",
        artifact_id="urn:uuid:00000000-0000-0000-0000-000000000002",
        created_at=created_at,
        producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:test"),
        project_id="zutfen:project:zadc",
        slice_id="TS-001",
        slice_instance_id="TS-001A",
        policy=PolicyReference(
            policy_id="zutfen:zadc-policy:standard@0.1.0",
            policy_source_sha="a" * 40,
            policy_digest="sha256:" + "b" * 64,
        ),
        provenance=Provenance(parent_artifact_ids=[]),
    )


class TestTimestampEquivalence:
    """Equivalent timestamp offsets produce identical canonical bytes/digests."""

    def test_utc_z_vs_zero_offset(self) -> None:
        """UTC with tzinfo=UTC should match UTC expressed as +00:00."""
        env_z = _make_envelope(datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC))
        env_offset = _make_envelope(
            datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone(timedelta(hours=0)))
        )
        data_z = env_z.model_dump(mode="json", by_alias=True)
        data_off = env_offset.model_dump(mode="json", by_alias=True)
        assert canonical_json_bytes(data_z) == canonical_json_bytes(data_off)
        assert compute_content_digest(env_z) == compute_content_digest(env_offset)

    def test_positive_offset_normalizes_to_utc(self) -> None:
        """+05:30 offset should normalize to UTC."""
        env_utc = _make_envelope(datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC))
        env_pos = _make_envelope(
            datetime(2026, 7, 31, 17, 30, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        )
        assert compute_content_digest(env_utc) == compute_content_digest(env_pos)

    def test_negative_offset_normalizes_to_utc(self) -> None:
        """-08:00 offset should normalize to UTC."""
        env_utc = _make_envelope(datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC))
        env_neg = _make_envelope(
            datetime(2026, 7, 31, 4, 0, 0, tzinfo=timezone(timedelta(hours=-8)))
        )
        assert compute_content_digest(env_utc) == compute_content_digest(env_neg)

    def test_uppercase_z_in_serialization(self) -> None:
        """Serialized timestamp uses uppercase Z, not +00:00."""
        env = _make_envelope(datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC))
        data = env.model_dump(mode="json", by_alias=True)
        text = data["created_at"]
        assert text.endswith("Z")
        assert "+00:00" not in text


class TestFractionalSeconds:
    """Deterministic fractional seconds handling."""

    def test_microseconds_preserved(self) -> None:
        """Microseconds are preserved in canonical output."""
        env = _make_envelope(datetime(2026, 7, 31, 12, 0, 0, 123456, tzinfo=UTC))
        data = env.model_dump(mode="json", by_alias=True)
        assert "123456" in data["created_at"]

    def test_no_fractional_seconds_when_zero(self) -> None:
        """Whole seconds have no fractional part."""
        env = _make_envelope(datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC))
        data = env.model_dump(mode="json", by_alias=True)
        assert data["created_at"] == "2026-07-31T12:00:00Z"

    def test_fractional_seconds_with_offset(self) -> None:
        """Fractional seconds survive UTC normalization."""
        env_utc = _make_envelope(datetime(2026, 7, 31, 12, 0, 0, 500000, tzinfo=UTC))
        env_off = _make_envelope(
            datetime(
                2026, 7, 31, 17, 30, 0, 500000, tzinfo=timezone(timedelta(hours=5, minutes=30))
            )
        )
        assert compute_content_digest(env_utc) == compute_content_digest(env_off)
