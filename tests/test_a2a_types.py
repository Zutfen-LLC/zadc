"""A2A-01/A2A-02/A2A-03: reusable timestamp, enum, and constrained-text helpers."""

from datetime import UTC, datetime
from typing import get_args

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from zadc.types import (
    CertificationResult,
    ConstrainedText,
    EpistemicStatus,
    EvidenceAvailability,
    ExactSubjectPolicy,
    ExecutorRecommendation,
    FindingSeverity,
    GitHubName,
    LaneClassification,
    LaneConclusion,
    MediaType,
    MismatchPolicy,
    ObservationSourceType,
    RefName,
    StableId,
    SubjectKind,
    Timestamp,
    coerce_timestamp,
    coerce_tuple,
    serialize_timestamp,
    validate_constrained_text,
    validate_github_name,
    validate_media_type,
    validate_ref_name,
    validate_stable_id,
)


class _TimestampHolder(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    value: Timestamp


class TestTimestampField:
    def test_accepts_aware_datetime_and_normalizes_to_utc(self) -> None:
        holder = _TimestampHolder(value=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC))
        assert holder.value.tzinfo is not None

    def test_accepts_valid_string(self) -> None:
        holder = _TimestampHolder(value="2026-07-31T12:00:00Z")  # type: ignore[arg-type]
        assert holder.value.year == 2026

    def test_rejects_naive_datetime(self) -> None:
        with pytest.raises(ValidationError):
            _TimestampHolder(value=datetime(2026, 7, 31, 12, 0, 0))

    def test_rejects_int(self) -> None:
        with pytest.raises((ValidationError, TypeError)):
            _TimestampHolder(value=1234567890)  # type: ignore[arg-type]

    def test_rejects_malformed_string(self) -> None:
        with pytest.raises(ValidationError):
            _TimestampHolder(value="2026-07-31 12:00:00Z")  # type: ignore[arg-type]

    def test_serializes_with_uppercase_z(self) -> None:
        holder = _TimestampHolder(value="2026-07-31T12:00:00.500000+02:00")  # type: ignore[arg-type]
        dumped = holder.model_dump(mode="json")
        assert dumped["value"].endswith("Z")
        assert "+02:00" not in dumped["value"]

    def test_coerce_timestamp_direct_type_error(self) -> None:
        with pytest.raises(TypeError):
            coerce_timestamp(3.14)

    def test_coerce_timestamp_direct_naive_datetime(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            coerce_timestamp(datetime(2026, 1, 1))

    def test_serialize_timestamp_direct(self) -> None:
        assert serialize_timestamp(datetime(2026, 1, 1, tzinfo=UTC)) == "2026-01-01T00:00:00Z"


class TestConstrainedText:
    def test_valid_multiline_prose(self) -> None:
        assert (
            validate_constrained_text("line one\nline two\ttabbed") == "line one\nline two\ttabbed"
        )

    def test_direct_type_error(self) -> None:
        with pytest.raises(TypeError):
            validate_constrained_text(123)  # type: ignore[arg-type]

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_constrained_text("")

    def test_rejects_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_constrained_text("   ")

    def test_rejects_leading_trailing_whitespace(self) -> None:
        with pytest.raises(ValueError, match="leading/trailing"):
            validate_constrained_text(" text ")

    def test_rejects_control_char(self) -> None:
        with pytest.raises(ValueError, match="disallowed"):
            validate_constrained_text("bad\x00text")

    class _Holder(BaseModel):
        model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
        value: ConstrainedText

    def test_via_pydantic_field(self) -> None:
        assert self._Holder(value="hello").value == "hello"

    def test_via_pydantic_field_rejects_empty(self) -> None:
        with pytest.raises(ValidationError):
            self._Holder(value="")


class TestStableId:
    def test_valid(self) -> None:
        assert validate_stable_id("REQ-1") == "REQ-1"
        assert validate_stable_id("lint.unit_test-01") == "lint.unit_test-01"

    def test_direct_type_error(self) -> None:
        with pytest.raises(TypeError):
            validate_stable_id(123)  # type: ignore[arg-type]

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_stable_id("")

    def test_rejects_bad_grammar(self) -> None:
        with pytest.raises(ValueError, match="grammar"):
            validate_stable_id("-bad")

    def test_rejects_control_char(self) -> None:
        with pytest.raises(ValueError):
            validate_stable_id("a\x00b")

    class _Holder(BaseModel):
        model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
        value: StableId

    def test_via_pydantic_field(self) -> None:
        assert self._Holder(value="REQ-1").value == "REQ-1"


class TestMediaType:
    def test_valid(self) -> None:
        assert validate_media_type("text/plain") == "text/plain"
        assert validate_media_type("application/vnd.foo+json") == "application/vnd.foo+json"

    def test_direct_type_error(self) -> None:
        with pytest.raises(TypeError):
            validate_media_type(123)  # type: ignore[arg-type]

    def test_rejects_missing_subtype(self) -> None:
        with pytest.raises(ValueError, match="grammar"):
            validate_media_type("text")

    class _Holder(BaseModel):
        model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
        value: MediaType

    def test_via_pydantic_field(self) -> None:
        assert self._Holder(value="text/plain").value == "text/plain"

    def test_via_pydantic_field_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            self._Holder(value="not-a-media-type")


class TestGitHubName:
    def test_valid(self) -> None:
        assert validate_github_name("Zutfen-LLC") == "Zutfen-LLC"

    def test_direct_type_error(self) -> None:
        with pytest.raises(TypeError):
            validate_github_name(123)  # type: ignore[arg-type]

    def test_rejects_leading_separator(self) -> None:
        with pytest.raises(ValueError, match="alphanumeric"):
            validate_github_name("-bad")

    class _Holder(BaseModel):
        model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
        value: GitHubName

    def test_via_pydantic_field(self) -> None:
        assert self._Holder(value="zadc").value == "zadc"


class TestRefName:
    def test_valid_with_slash(self) -> None:
        assert validate_ref_name("feat/zadc-001a2a") == "feat/zadc-001a2a"

    def test_direct_type_error(self) -> None:
        with pytest.raises(TypeError):
            validate_ref_name(123)  # type: ignore[arg-type]

    def test_rejects_bad_grammar(self) -> None:
        with pytest.raises(ValueError, match="alphanumeric"):
            validate_ref_name("/bad")

    class _Holder(BaseModel):
        model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
        value: RefName

    def test_via_pydantic_field(self) -> None:
        assert self._Holder(value="main").value == "main"


class TestCoerceTuple:
    def test_list_becomes_tuple(self) -> None:
        assert coerce_tuple([1, 2, 3]) == (1, 2, 3)

    def test_tuple_passthrough(self) -> None:
        assert coerce_tuple((1, 2)) == (1, 2)

    def test_other_passthrough(self) -> None:
        assert coerce_tuple("not-a-list") == "not-a-list"
        assert coerce_tuple(None) is None


class TestSharedEnums:
    """Every required Literal value from A2A-03 is present."""

    def test_epistemic_status(self) -> None:
        assert set(get_args(EpistemicStatus)) == {
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
        }

    def test_mismatch_policy(self) -> None:
        assert set(get_args(MismatchPolicy)) == {"abort", "reconcile_with_record"}

    def test_exact_subject_policy(self) -> None:
        assert set(get_args(ExactSubjectPolicy)) == {
            "final_pr_head",
            "certified_code_with_evidence_tail",
        }

    def test_finding_severity(self) -> None:
        assert set(get_args(FindingSeverity)) == {"blocker", "major", "minor", "note"}

    def test_executor_recommendation(self) -> None:
        assert set(get_args(ExecutorRecommendation)) == {
            "green_for_review",
            "red",
            "blocked",
            "inconclusive",
        }

    def test_subject_kind(self) -> None:
        assert set(get_args(SubjectKind)) == {
            "commit",
            "pr_head",
            "synthetic_merge",
            "merge_commit",
        }

    def test_lane_classification(self) -> None:
        assert set(get_args(LaneClassification)) == {"mandatory", "advisory"}

    def test_lane_conclusion(self) -> None:
        assert set(get_args(LaneConclusion)) == {
            "pass",
            "fail",
            "skipped",
            "cancelled",
            "timed_out",
            "unavailable",
        }

    def test_certification_result(self) -> None:
        assert set(get_args(CertificationResult)) == {"pass", "fail", "inconclusive"}

    def test_evidence_availability(self) -> None:
        assert set(get_args(EvidenceAvailability)) == {"available", "unavailable"}

    def test_observation_source_type(self) -> None:
        assert set(get_args(ObservationSourceType)) == {
            "git",
            "github",
            "ci",
            "deployment",
            "billing",
            "service",
            "other",
        }
