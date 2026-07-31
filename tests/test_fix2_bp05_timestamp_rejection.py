"""FIX2-BP-05: ZADC RFC 3339 runtime rejection.

Tests that the ZADC Timestamp v0.1 grammar rejects every malformed form,
including all datetime.fromisoformat over-acceptance examples.
"""

import pytest

from zadc.types import validate_timestamp


class TestTimestampRuntimeRejection:
    """Reject every malformed timestamp form."""

    @pytest.mark.parametrize(
        "bad_ts",
        [
            # Space separators
            "2026-07-31 12:00:00Z",
            "2026-07-31 12:00:00",
            # Arbitrary separator (X)
            "2026-07-31X12:00:00Z",
            # Basic date/time forms (no separators)
            "20260731T120000Z",
            # Week dates
            "2026-W31-1T12:00:00Z",
            # Ordinal dates
            "2026-212T12:00:00Z",
            # Offsets without colon
            "2026-07-31T12:00:00+0500",
            "2026-07-31T12:00:00-0500",
            # Timezone-free strings
            "2026-07-31T12:00:00",
            # Lowercase t
            "2026-07-31t12:00:00Z",
            # Lowercase z
            "2026-07-31T12:00:00z",
            # >6 fractional digits
            "2026-07-31T12:00:00.1234567Z",
            "2026-07-31T12:00:00.123456789Z",
            # Leap seconds
            "2026-07-31T12:00:60Z",
            "2026-07-31T23:59:60Z",
            # Unknown offset -00:00
            "2026-07-31T12:00:00-00:00",
            # Invalid dates
            "2026-13-01T12:00:00Z",  # month 13
            "2026-00-01T12:00:00Z",  # month 0
            "2026-02-30T12:00:00Z",  # Feb 30
            "2026-02-31T12:00:00Z",  # Feb 31
            "2026-04-31T12:00:00Z",  # Apr 31
            "2025-02-29T12:00:00Z",  # Feb 29 on non-leap year
            "2026-01-00T12:00:00Z",  # day 0
            "2026-01-32T12:00:00Z",  # day 32
            # Invalid times
            "2026-07-31T24:00:00Z",  # hour 24
            "2026-07-31T12:60:00Z",  # minute 60
            "2026-07-31T12:00:61Z",  # second 61
            # Invalid offsets
            "2026-07-31T12:00:00+24:00",  # offset hour 24
            "2026-07-31T12:00:00+12:60",  # offset minute 60
            # Trailing data
            "2026-07-31T12:00:00Z extra",
            "2026-07-31T12:00:00ZEXTRA",
            "2026-07-31T12:00:00Z ",
        ],
    )
    def test_reject_malformed_timestamps(self, bad_ts: str) -> None:
        with pytest.raises((ValueError, TypeError)):
            validate_timestamp(bad_ts)

    def test_reject_empty_string(self) -> None:
        with pytest.raises(ValueError):
            validate_timestamp("")

    def test_reject_non_string(self) -> None:
        with pytest.raises(TypeError):
            validate_timestamp(12345)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "bad_ts",
        [
            # fromisoformat accepts these, but we don't
            "2026-07-31T12:00:00.1234561Z",  # 7 digits
            "2026-07-31T12:00:00.12345678Z",  # 8 digits
        ],
    )
    def test_reject_excessive_fractional_precision(self, bad_ts: str) -> None:
        """Reject >6 fractional digits rather than silently truncating."""
        with pytest.raises(ValueError):
            validate_timestamp(bad_ts)
