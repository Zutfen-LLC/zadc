"""A2B1: the ReviewReport artifact and its supporting models."""

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tests.a2b1_factories import (
    DIGEST_C,
    EXECUTOR_ID,
    REVIEWER_ID,
    SHA_B,
    build_review_report,
)
from zadc.canonical import canonical_json_text
from zadc.digests import compute_content_digest, seal_artifact, verify_content_digest
from zadc.errors import DigestMismatchError
from zadc.models.review_report import (
    ArtifactFindingLocation,
    FileFindingLocation,
    Finding,
    GeneralFindingLocation,
    ReviewedFile,
    ReviewerIdentity,
    ReviewIndependence,
    ReviewReport,
    ReviewSubject,
)
from zadc.models.shared import ArtifactReference


class TestReviewReportConstruction:
    def test_valid_review_report(self) -> None:
        report = build_review_report()
        assert report.artifact_type == "review_report"
        assert report.findings[0].finding_id == "F-1"

    def test_rejects_wrong_artifact_type(self) -> None:
        with pytest.raises(ValidationError):
            build_review_report(artifact_type="decision_record")

    def test_rejects_extra_top_level_field(self) -> None:
        with pytest.raises(ValidationError):
            build_review_report(unexpected_field="nope")

    def test_frozen(self) -> None:
        report = build_review_report()
        with pytest.raises(ValidationError):
            report.artifact_id = "urn:uuid:00000000-0000-0000-0000-000000000099"

    def test_list_and_tuple_inputs_are_equivalent(self) -> None:
        as_list = build_review_report(limitations=["a", "b"])
        as_tuple = build_review_report(limitations=("a", "b"))
        assert as_list.limitations == as_tuple.limitations == ("a", "b")
        assert isinstance(as_list.limitations, tuple)

    def test_review_id_must_equal_artifact_id(self) -> None:
        with pytest.raises(ValidationError, match="review_id"):
            build_review_report(review_id="urn:uuid:00000000-0000-0000-0000-000000000999")

    def test_reviewer_must_match_producer_actor_id(self) -> None:
        with pytest.raises(ValidationError, match="reviewer"):
            build_review_report(
                reviewer=ReviewerIdentity(actor_type="human", actor_id="zutfen:human:someone-else")
            )

    def test_reviewer_must_match_producer_actor_type(self) -> None:
        from zadc import ProducerIdentity

        with pytest.raises(ValidationError, match="reviewer"):
            build_review_report(producer=ProducerIdentity(actor_type="agent", actor_id=REVIEWER_ID))

    def test_independence_satisfied_requires_different_executor(self) -> None:
        with pytest.raises(ValidationError, match="independence"):
            build_review_report(
                independence=ReviewIndependence(executor_actor_id=REVIEWER_ID, satisfied=True)
            )

    def test_independence_not_satisfied_allows_same_executor(self) -> None:
        report = build_review_report(
            independence=ReviewIndependence(executor_actor_id=REVIEWER_ID, satisfied=False)
        )
        assert report.independence.satisfied is False

    def test_independence_satisfied_with_different_executor_allowed(self) -> None:
        report = build_review_report(
            independence=ReviewIndependence(executor_actor_id=EXECUTOR_ID, satisfied=True)
        )
        assert report.independence.satisfied is True

    def test_duplicate_finding_ids_rejected(self) -> None:
        finding = Finding(
            finding_id="F-DUP",
            severity="minor",
            status="open",
            location=GeneralFindingLocation(location_type="general", description="general note"),
            statement="x",
            rationale="y",
            resolution_refs=(),
        )
        with pytest.raises(ValidationError, match="finding_id"):
            build_review_report(findings=(finding, finding))


class TestReviewerIdentity:
    def test_agent_reviewer_allowed(self) -> None:
        identity = ReviewerIdentity(
            actor_type="agent",
            actor_id="zutfen:agent:claude",
            model="claude-sonnet-5",
            provider="anthropic",
        )
        assert identity.model == "claude-sonnet-5"

    def test_rejects_non_human_non_agent_actor_type(self) -> None:
        with pytest.raises(ValidationError):
            ReviewerIdentity(actor_type="ci", actor_id="zutfen:ci:runner")  # type: ignore[arg-type]


class TestReviewSubject:
    def test_duplicate_certification_manifest_ids_rejected(self) -> None:
        manifest_id = "urn:uuid:00000000-0000-0000-0000-000000000006"
        with pytest.raises(ValidationError, match="certification_manifest_ids"):
            ReviewSubject(
                repository_id="github:Zutfen-LLC/zadc",
                review_subject_sha=SHA_B,
                packet_digest=DIGEST_C,
                certification_manifest_ids=(manifest_id, manifest_id),
            )


class TestReviewedFile:
    def test_end_line_without_start_line_rejected(self) -> None:
        with pytest.raises(ValidationError, match="start_line"):
            ReviewedFile(path="a.py", start_line=None, end_line=5)

    def test_end_line_before_start_line_rejected(self) -> None:
        with pytest.raises(ValidationError, match="end_line"):
            ReviewedFile(path="a.py", start_line=10, end_line=5)

    def test_start_line_only_allowed(self) -> None:
        reviewed = ReviewedFile(path="a.py", start_line=1, end_line=None)
        assert reviewed.end_line is None

    def test_equal_start_and_end_allowed(self) -> None:
        reviewed = ReviewedFile(path="a.py", start_line=3, end_line=3)
        assert reviewed.end_line == 3


class TestFindingLocationDiscriminatedUnion:
    def test_file_location(self) -> None:
        loc = FileFindingLocation(location_type="file", path="a.py", start_line=1, end_line=2)
        assert loc.path == "a.py"

    def test_file_location_end_before_start_rejected(self) -> None:
        with pytest.raises(ValidationError, match="end_line"):
            FileFindingLocation(location_type="file", path="a.py", start_line=5, end_line=1)

    def test_file_location_end_without_start_rejected(self) -> None:
        with pytest.raises(ValidationError, match="start_line"):
            FileFindingLocation(location_type="file", path="a.py", start_line=None, end_line=1)

    def test_artifact_location(self) -> None:
        loc = ArtifactFindingLocation(
            location_type="artifact", artifact_id="urn:uuid:00000000-0000-0000-0000-000000000050"
        )
        assert loc.location_type == "artifact"

    def test_general_location(self) -> None:
        loc = GeneralFindingLocation(location_type="general", description="cross-cutting concern")
        assert loc.description == "cross-cutting concern"

    def test_file_location_rejects_artifact_field(self) -> None:
        with pytest.raises(ValidationError):
            FileFindingLocation(
                location_type="file",
                path="a.py",
                artifact_id="urn:uuid:00000000-0000-0000-0000-000000000050",
            )  # type: ignore[call-arg]

    def test_artifact_location_rejects_path_field(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactFindingLocation(
                location_type="artifact",
                artifact_id="urn:uuid:00000000-0000-0000-0000-000000000050",
                path="a.py",
            )  # type: ignore[call-arg]

    def test_general_location_rejects_path_field(self) -> None:
        with pytest.raises(ValidationError):
            GeneralFindingLocation(location_type="general", description="note", path="a.py")  # type: ignore[call-arg]

    def test_discriminator_rejects_unknown_location_type(self) -> None:
        with pytest.raises(ValidationError):
            Finding(
                finding_id="F-9",
                severity="note",
                status="open",
                location={"location_type": "unknown"},  # type: ignore[arg-type]
                statement="x",
                rationale="y",
                resolution_refs=(),
            )


class TestFinding:
    def _location(self) -> GeneralFindingLocation:
        return GeneralFindingLocation(location_type="general", description="note")

    def test_open_status_allows_empty_resolution_refs(self) -> None:
        finding = Finding(
            finding_id="F-1",
            severity="minor",
            status="open",
            location=self._location(),
            statement="x",
            rationale="y",
            resolution_refs=(),
        )
        assert finding.resolution_refs == ()

    def test_resolved_requires_resolution_ref(self) -> None:
        with pytest.raises(ValidationError, match="resolved"):
            Finding(
                finding_id="F-1",
                severity="minor",
                status="resolved",
                location=self._location(),
                statement="x",
                rationale="y",
                resolution_refs=(),
            )

    def test_resolved_with_resolution_ref_accepted(self) -> None:
        finding = Finding(
            finding_id="F-1",
            severity="minor",
            status="resolved",
            location=self._location(),
            statement="x",
            rationale="y",
            resolution_refs=(
                ArtifactReference(
                    artifact_id="urn:uuid:00000000-0000-0000-0000-000000000050",
                    content_digest=DIGEST_C,
                ),
            ),
        )
        assert len(finding.resolution_refs) == 1

    def test_accepted_risk_requires_resolution_ref(self) -> None:
        with pytest.raises(ValidationError, match="accepted_risk"):
            Finding(
                finding_id="F-1",
                severity="minor",
                status="accepted_risk",
                location=self._location(),
                statement="x",
                rationale="y",
                resolution_refs=(),
            )

    def test_invalid_status_allows_empty_resolution_refs(self) -> None:
        finding = Finding(
            finding_id="F-1",
            severity="minor",
            status="invalid",
            location=self._location(),
            statement="x",
            rationale="y",
            resolution_refs=(),
        )
        assert finding.status == "invalid"


class TestReviewReportDigestSealingAndCanonicalization:
    def test_seal_preserves_concrete_class(self) -> None:
        report = build_review_report()
        sealed = seal_artifact(report)
        assert type(sealed) is ReviewReport
        assert sealed.provenance.content_digest is not None

    def test_verify_content_digest_roundtrip(self) -> None:
        sealed = seal_artifact(build_review_report())
        verify_content_digest(sealed)

    def test_tamper_top_level_field_detected(self) -> None:
        sealed = seal_artifact(build_review_report())
        data = json.loads(canonical_json_text(sealed))
        data["reviewer_recommendation"] = "red"
        tampered = ReviewReport.model_validate(data)
        with pytest.raises(DigestMismatchError):
            verify_content_digest(tampered)

    def test_tamper_nested_field_detected(self) -> None:
        sealed = seal_artifact(build_review_report())
        data = json.loads(canonical_json_text(sealed))
        data["findings"][0]["severity"] = "blocker"
        tampered = ReviewReport.model_validate(data)
        with pytest.raises(DigestMismatchError):
            verify_content_digest(tampered)

    def test_canonical_round_trip_reload(self) -> None:
        sealed = seal_artifact(build_review_report())
        data = json.loads(canonical_json_text(sealed))
        reloaded = ReviewReport.model_validate(data)
        assert reloaded == sealed
        verify_content_digest(reloaded)

    def test_canonical_output_invariant_across_list_and_tuple_input(self) -> None:
        as_list = build_review_report(limitations=["one limitation"])
        as_tuple = build_review_report(limitations=("one limitation",))
        digest_list = compute_content_digest(as_list)
        digest_tuple = compute_content_digest(as_tuple)
        assert digest_list == digest_tuple

    def test_canonical_output_invariant_across_field_order(self) -> None:
        report = build_review_report()
        kwargs = report.model_dump(mode="python", by_alias=True)
        reordered_kwargs = dict(reversed(list(kwargs.items())))
        reordered = ReviewReport.model_validate(reordered_kwargs)
        assert compute_content_digest(report) == compute_content_digest(reordered)

    def test_created_at_field_survives_reload(self) -> None:
        sealed = seal_artifact(build_review_report())
        data = json.loads(canonical_json_text(sealed))
        reloaded = ReviewReport.model_validate(data)
        assert reloaded.created_at == datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
