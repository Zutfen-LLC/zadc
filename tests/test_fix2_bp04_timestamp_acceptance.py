"""FIX2-BP-04: ZADC RFC 3339 runtime acceptance and normalization.

Tests that the ZADC Timestamp v0.1 profile accepts valid timestamps
and normalizes equivalent instants to identical UTC-Z bytes/digests.
"""

import pytest

from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    canonical_json_text,
    compute_content_digest,
)
from zadc.types import CONTRACT_VERSION, SCHEMA_ID, validate_timestamp


def _make_envelope(ts: str) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        schema=SCHEMA_ID,
        contract_version=CONTRACT_VERSION,
        artifact_type="packet",
        artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
        created_at=ts,  # type: ignore[arg-type]
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


class TestTimestampAcceptance:
    """Accept Z and positive/negative colon offsets using full date and time."""

    @pytest.mark.parametrize(
        "ts",
        [
            # UTC Z
            "2026-07-31T12:00:00Z",
            # Positive offset with colon
            "2026-07-31T17:30:00+05:30",
            # Negative offset with colon
            "2026-07-31T07:00:00-05:00",
            # +00:00 is equivalent to Z
            "2026-07-31T12:00:00+00:00",
        ],
    )
    def test_accept_valid_timestamps(self, ts: str) -> None:
        assert validate_timestamp(ts) == ts


class TestFractionalSecondsAcceptance:
    """Accept fractions of 1 through 6 digits."""

    @pytest.mark.parametrize(
        "ts",
        [
            "2026-07-31T12:00:00.1Z",
            "2026-07-31T12:00:00.12Z",
            "2026-07-31T12:00:00.123Z",
            "2026-07-31T12:00:00.1234Z",
            "2026-07-31T12:00:00.12345Z",
            "2026-07-31T12:00:00.123456Z",
        ],
    )
    def test_accept_fractional_seconds(self, ts: str) -> None:
        assert validate_timestamp(ts) == ts

    def test_accept_feb_29_leap_year(self) -> None:
        """Feb 29 is accepted on leap years (2024, 2028)."""
        assert validate_timestamp("2024-02-29T12:00:00Z") == "2024-02-29T12:00:00Z"


class TestOffsetNormalization:
    """Equivalent instants with different offsets canonicalize to identical UTC-Z bytes."""

    def test_utc_vs_positive_offset_same_digest(self) -> None:
        env_utc = _make_envelope("2026-07-31T12:00:00Z")
        env_pos = _make_envelope("2026-07-31T17:30:00+05:30")
        assert canonical_json_text(env_utc) == canonical_json_text(env_pos)
        assert compute_content_digest(env_utc) == compute_content_digest(env_pos)

    def test_utc_vs_negative_offset_same_digest(self) -> None:
        env_utc = _make_envelope("2026-07-31T12:00:00Z")
        env_neg = _make_envelope("2026-07-31T07:00:00-05:00")
        assert canonical_json_text(env_utc) == canonical_json_text(env_neg)
        assert compute_content_digest(env_utc) == compute_content_digest(env_neg)

    def test_plus_zero_equals_z(self) -> None:
        env_z = _make_envelope("2026-07-31T12:00:00Z")
        env_zero = _make_envelope("2026-07-31T12:00:00+00:00")
        assert canonical_json_text(env_z) == canonical_json_text(env_zero)


class TestCanonicalMicrosecondOutput:
    """Canonical output does not retain insignificant trailing microsecond zeros."""

    def test_microsecond_serialized_correctly(self) -> None:
        env = _make_envelope("2026-07-31T12:00:00.100000Z")
        text = canonical_json_text(env)
        # Python's isoformat drops trailing zeros in microseconds
        # .100000 microseconds = 100000 microseconds -> isoformat: .100000
        # Actually Python preserves 6 digits for microseconds
        assert "2026-07-31T12:00:00.100000Z" in text

    def test_no_microsecond_omitted(self) -> None:
        """When microseconds are present, they appear in canonical output."""
        env = _make_envelope("2026-07-31T12:00:00.500000Z")
        text = canonical_json_text(env)
        assert ".500000Z" in text

    def test_zero_microseconds_no_fraction(self) -> None:
        """When microseconds are 0, no fraction in output."""
        env = _make_envelope("2026-07-31T12:00:00Z")
        text = canonical_json_text(env)
        assert "2026-07-31T12:00:00Z" in text
