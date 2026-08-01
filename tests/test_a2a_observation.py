"""A2A-08: the Observation artifact."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tests.a2a_factories import build_observation


class TestObservationConstruction:
    def test_valid(self) -> None:
        obs = build_observation()
        assert obs.artifact_type == "observation"
        assert obs.epistemic_status == "LIVE_SOURCE_OBSERVED"

    def test_rejects_wrong_artifact_type(self) -> None:
        with pytest.raises(ValidationError):
            build_observation(artifact_type="packet")

    def test_rejects_extra_top_level_field(self) -> None:
        with pytest.raises(ValidationError):
            build_observation(unexpected="nope")

    def test_freshness_seconds_optional(self) -> None:
        obs = build_observation(freshness_seconds=None)
        assert obs.freshness_seconds is None

    def test_rejects_zero_freshness_seconds(self) -> None:
        with pytest.raises(ValidationError):
            build_observation(freshness_seconds=0)

    def test_rejects_negative_freshness_seconds(self) -> None:
        with pytest.raises(ValidationError):
            build_observation(freshness_seconds=-1)

    def test_expires_at_optional(self) -> None:
        obs = build_observation(expires_at=None)
        assert obs.expires_at is None

    def test_expires_at_after_observed_at_is_valid(self) -> None:
        obs = build_observation(
            observed_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
            expires_at=datetime(2026, 7, 31, 12, 10, 0, tzinfo=UTC),
        )
        assert obs.expires_at is not None

    def test_rejects_expires_at_equal_to_observed_at(self) -> None:
        t = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
        with pytest.raises(ValidationError, match="expires_at"):
            build_observation(observed_at=t, expires_at=t)

    def test_rejects_expires_at_before_observed_at(self) -> None:
        with pytest.raises(ValidationError, match="expires_at"):
            build_observation(
                observed_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
                expires_at=datetime(2026, 7, 31, 11, 0, 0, tzinfo=UTC),
            )

    def test_accepts_every_epistemic_status_value(self) -> None:
        for status in (
            "PROPOSED",
            "AGENT_REPORTED",
            "LOCALLY_OBSERVED",
            "CI_OBSERVED",
            "LIVE_SOURCE_OBSERVED",
            "INDEPENDENTLY_REPRODUCED",
            "VERIFIED",
            "CONTRADICTED",
            "STALE",
            "SUPERSEDED",
        ):
            obs = build_observation(epistemic_status=status)
            assert obs.epistemic_status == status
