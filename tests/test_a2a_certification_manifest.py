"""A2A-06: the CertificationManifest artifact and its LaneResult submodel."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tests.a2a_factories import SHA_B, build_certification_manifest
from zadc.models.certification_manifest import LaneResult
from zadc.models.shared import ExactSubject


class TestCertificationManifestConstruction:
    def test_valid(self) -> None:
        manifest = build_certification_manifest()
        assert manifest.artifact_type == "certification_manifest"
        assert manifest.result == "pass"

    def test_rejects_wrong_artifact_type(self) -> None:
        with pytest.raises(ValidationError):
            build_certification_manifest(artifact_type="packet")

    def test_rejects_extra_top_level_field(self) -> None:
        with pytest.raises(ValidationError):
            build_certification_manifest(unexpected="nope")


class TestLaneResult:
    def test_valid(self) -> None:
        lane = LaneResult(
            lane_id="test",
            classification="mandatory",
            conclusion="pass",
            started_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
            completed_at=datetime(2026, 7, 31, 12, 5, 0, tzinfo=UTC),
            command_or_workflow="make check",
            evidence_refs=(),
        )
        assert lane.conclusion == "pass"

    def test_completed_at_equal_started_at_is_valid(self) -> None:
        t = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
        lane = LaneResult(
            lane_id="test",
            classification="advisory",
            conclusion="skipped",
            started_at=t,
            completed_at=t,
            command_or_workflow="make check",
            evidence_refs=(),
        )
        assert lane.started_at == lane.completed_at

    def test_rejects_completed_before_started(self) -> None:
        with pytest.raises(ValidationError, match="completed_at"):
            LaneResult(
                lane_id="test",
                classification="mandatory",
                conclusion="pass",
                started_at=datetime(2026, 7, 31, 12, 5, 0, tzinfo=UTC),
                completed_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
                command_or_workflow="make check",
                evidence_refs=(),
            )


class TestCertificationManifestInvariants:
    def test_rejects_duplicate_lane_ids(self) -> None:
        t0 = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
        t1 = datetime(2026, 7, 31, 12, 5, 0, tzinfo=UTC)
        lane = LaneResult(
            lane_id="test",
            classification="mandatory",
            conclusion="pass",
            started_at=t0,
            completed_at=t1,
            command_or_workflow="make check",
            evidence_refs=(),
        )
        with pytest.raises(ValidationError, match="lane_id"):
            build_certification_manifest(lanes=[lane, lane])

    def test_result_pass_requires_all_mandatory_lanes_pass(self) -> None:
        t0 = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
        t1 = datetime(2026, 7, 31, 12, 5, 0, tzinfo=UTC)
        failing_mandatory = LaneResult(
            lane_id="test",
            classification="mandatory",
            conclusion="fail",
            started_at=t0,
            completed_at=t1,
            command_or_workflow="make check",
            evidence_refs=(),
        )
        with pytest.raises(ValidationError, match="mandatory lane"):
            build_certification_manifest(lanes=[failing_mandatory], result="pass")

    def test_result_pass_ignores_failing_advisory_lane(self) -> None:
        t0 = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
        t1 = datetime(2026, 7, 31, 12, 5, 0, tzinfo=UTC)
        passing_mandatory = LaneResult(
            lane_id="test",
            classification="mandatory",
            conclusion="pass",
            started_at=t0,
            completed_at=t1,
            command_or_workflow="make check",
            evidence_refs=(),
        )
        failing_advisory = LaneResult(
            lane_id="bench",
            classification="advisory",
            conclusion="fail",
            started_at=t0,
            completed_at=t1,
            command_or_workflow="make bench",
            evidence_refs=(),
        )
        manifest = build_certification_manifest(
            lanes=[passing_mandatory, failing_advisory], result="pass"
        )
        assert manifest.result == "pass"

    def test_result_fail_allowed_with_failing_mandatory_lane(self) -> None:
        t0 = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
        t1 = datetime(2026, 7, 31, 12, 5, 0, tzinfo=UTC)
        failing_mandatory = LaneResult(
            lane_id="test",
            classification="mandatory",
            conclusion="fail",
            started_at=t0,
            completed_at=t1,
            command_or_workflow="make check",
            evidence_refs=(),
        )
        manifest = build_certification_manifest(lanes=[failing_mandatory], result="fail")
        assert manifest.result == "fail"

    def test_pr_head_subject_reused_from_shared_model(self) -> None:
        manifest = build_certification_manifest(
            subject=ExactSubject(
                repository_id="github:Zutfen-LLC/zadc",
                subject_kind="commit",
                subject_sha=SHA_B,
            )
        )
        assert manifest.subject.subject_kind == "commit"
