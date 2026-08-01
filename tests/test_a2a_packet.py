"""A2A-04: the Packet artifact and its supporting models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tests.a2a_factories import SHA_A, build_packet
from zadc.models.packet import (
    DependencyPin,
    Packet,
    PacketAuthorization,
    PacketReview,
    PacketScope,
    RepositoryTarget,
    Requirement,
    VerificationRequirements,
    WorkStartAuthorization,
)
from zadc.models.shared import ArtifactReference


class TestPacketConstruction:
    def test_valid_packet(self) -> None:
        packet = build_packet()
        assert packet.artifact_type == "packet"
        assert packet.requirements[0].requirement_id == "REQ-1"

    def test_rejects_wrong_artifact_type(self) -> None:
        with pytest.raises(ValidationError):
            build_packet(artifact_type="completion_report")

    def test_rejects_extra_top_level_field(self) -> None:
        with pytest.raises(ValidationError):
            build_packet(unexpected_field="nope")

    def test_frozen(self) -> None:
        packet = build_packet()
        with pytest.raises(ValidationError):
            packet.artifact_id = "urn:uuid:00000000-0000-0000-0000-000000000099"

    def test_list_and_tuple_inputs_are_equivalent(self) -> None:
        as_list = build_packet(stop_conditions=["a", "b"])
        as_tuple = build_packet(stop_conditions=("a", "b"))
        assert as_list.stop_conditions == as_tuple.stop_conditions == ("a", "b")
        assert isinstance(as_list.stop_conditions, tuple)


class TestPacketAuthorization:
    def test_no_expiry(self) -> None:
        auth = PacketAuthorization(
            authorized_by="zutfen:human:eric",
            authorized_at=datetime(2026, 7, 31, 11, 0, 0, tzinfo=UTC),
        )
        assert auth.expires_at is None

    def test_expiry_after_authorization(self) -> None:
        auth = PacketAuthorization(
            authorized_by="zutfen:human:eric",
            authorized_at=datetime(2026, 7, 31, 11, 0, 0, tzinfo=UTC),
            expires_at=datetime(2026, 8, 1, 11, 0, 0, tzinfo=UTC),
        )
        assert auth.expires_at is not None

    def test_rejects_expiry_equal_to_authorization(self) -> None:
        with pytest.raises(ValidationError, match="expires_at"):
            PacketAuthorization(
                authorized_by="zutfen:human:eric",
                authorized_at=datetime(2026, 7, 31, 11, 0, 0, tzinfo=UTC),
                expires_at=datetime(2026, 7, 31, 11, 0, 0, tzinfo=UTC),
            )

    def test_rejects_expiry_before_authorization(self) -> None:
        with pytest.raises(ValidationError, match="expires_at"):
            PacketAuthorization(
                authorized_by="zutfen:human:eric",
                authorized_at=datetime(2026, 7, 31, 11, 0, 0, tzinfo=UTC),
                expires_at=datetime(2026, 7, 31, 10, 0, 0, tzinfo=UTC),
            )


class TestRepositoryTarget:
    def test_no_pull_request(self) -> None:
        target = RepositoryTarget(
            repository_id="github:Zutfen-LLC/zadc",
            provider="github",
            owner="Zutfen-LLC",
            name="zadc",
        )
        assert target.pull_request is None

    def test_positive_pull_request(self) -> None:
        target = RepositoryTarget(
            repository_id="github:Zutfen-LLC/zadc",
            provider="github",
            owner="Zutfen-LLC",
            name="zadc",
            pull_request=1,
        )
        assert target.pull_request == 1

    def test_rejects_zero_pull_request(self) -> None:
        with pytest.raises(ValidationError):
            RepositoryTarget(
                repository_id="github:Zutfen-LLC/zadc",
                provider="github",
                owner="Zutfen-LLC",
                name="zadc",
                pull_request=0,
            )

    def test_rejects_negative_pull_request(self) -> None:
        with pytest.raises(ValidationError):
            RepositoryTarget(
                repository_id="github:Zutfen-LLC/zadc",
                provider="github",
                owner="Zutfen-LLC",
                name="zadc",
                pull_request=-1,
            )

    def test_rejects_non_github_provider(self) -> None:
        with pytest.raises(ValidationError):
            RepositoryTarget(
                repository_id="github:Zutfen-LLC/zadc",
                provider="gitlab",  # type: ignore[arg-type]
                owner="Zutfen-LLC",
                name="zadc",
            )


class TestWorkStartAuthorization:
    def test_abort_policy(self) -> None:
        wsa = WorkStartAuthorization(expected_sha=SHA_A, mismatch_policy="abort")
        assert wsa.mismatch_policy == "abort"

    def test_reconcile_policy(self) -> None:
        wsa = WorkStartAuthorization(expected_sha=SHA_A, mismatch_policy="reconcile_with_record")
        assert wsa.mismatch_policy == "reconcile_with_record"

    def test_rejects_bad_sha(self) -> None:
        with pytest.raises(ValidationError):
            WorkStartAuthorization(expected_sha="not-a-sha", mismatch_policy="abort")


class TestPacketScope:
    def test_lists_normalize_to_tuples(self) -> None:
        scope = PacketScope(
            allowed_paths=["src/**"],  # type: ignore[arg-type]
            prohibited_paths=[],  # type: ignore[arg-type]
            allowed_operations=["edit"],  # type: ignore[arg-type]
            prohibited_operations=[],  # type: ignore[arg-type]
        )
        assert isinstance(scope.allowed_paths, tuple)
        assert scope.prohibited_paths == ()


class TestRequirement:
    def test_valid(self) -> None:
        req = Requirement(
            requirement_id="REQ-1", statement="Do the thing", acceptance_criteria=("it works",)
        )
        assert req.acceptance_criteria == ("it works",)

    def test_rejects_bad_requirement_id(self) -> None:
        with pytest.raises(ValidationError):
            Requirement(requirement_id="-bad", statement="x", acceptance_criteria=())


class TestDependencyPin:
    def test_valid(self) -> None:
        pin = DependencyPin(
            repository_id="github:Zutfen-LLC/engram", sha=SHA_A, cleanliness_required=True
        )
        assert pin.cleanliness_required is True


class TestVerificationRequirements:
    def test_valid_disjoint_lanes(self) -> None:
        vr = VerificationRequirements(
            mandatory_lanes=("lint", "test"),
            advisory_lanes=("bench",),
            exact_subject_policy="final_pr_head",
            synthetic_merge_required=False,
        )
        assert vr.mandatory_lanes == ("lint", "test")

    def test_empty_lanes_allowed(self) -> None:
        vr = VerificationRequirements(
            mandatory_lanes=(),
            advisory_lanes=(),
            exact_subject_policy="final_pr_head",
            synthetic_merge_required=False,
        )
        assert vr.mandatory_lanes == ()

    def test_rejects_duplicate_mandatory_lanes(self) -> None:
        with pytest.raises(ValidationError, match="mandatory_lanes"):
            VerificationRequirements(
                mandatory_lanes=("lint", "lint"),
                advisory_lanes=(),
                exact_subject_policy="final_pr_head",
                synthetic_merge_required=False,
            )

    def test_rejects_duplicate_advisory_lanes(self) -> None:
        with pytest.raises(ValidationError, match="advisory_lanes"):
            VerificationRequirements(
                mandatory_lanes=(),
                advisory_lanes=("bench", "bench"),
                exact_subject_policy="final_pr_head",
                synthetic_merge_required=False,
            )

    def test_rejects_overlapping_lanes(self) -> None:
        with pytest.raises(ValidationError, match="overlap"):
            VerificationRequirements(
                mandatory_lanes=("lint",),
                advisory_lanes=("lint",),
                exact_subject_policy="final_pr_head",
                synthetic_merge_required=False,
            )

    def test_synthetic_merge_required_true(self) -> None:
        vr = VerificationRequirements(
            mandatory_lanes=(),
            advisory_lanes=(),
            exact_subject_policy="certified_code_with_evidence_tail",
            synthetic_merge_required=True,
        )
        assert vr.synthetic_merge_required is True


class TestPacketReview:
    def test_valid(self) -> None:
        review = PacketReview(independent_review_required=True, minimum_severity_blocking="blocker")
        assert review.minimum_severity_blocking == "blocker"


class TestPacketInvariants:
    def test_rejects_duplicate_requirement_ids(self) -> None:
        with pytest.raises(ValidationError, match="requirement_id"):
            build_packet(
                requirements=(
                    Requirement(requirement_id="REQ-1", statement="a", acceptance_criteria=()),
                    Requirement(requirement_id="REQ-1", statement="b", acceptance_criteria=()),
                )
            )

    def test_accepts_unique_requirement_ids(self) -> None:
        packet = build_packet(
            requirements=(
                Requirement(requirement_id="REQ-1", statement="a", acceptance_criteria=()),
                Requirement(requirement_id="REQ-2", statement="b", acceptance_criteria=()),
            )
        )
        assert len(packet.requirements) == 2

    def test_supersedes_none_is_valid(self) -> None:
        packet = build_packet(supersedes=None)
        assert packet.supersedes is None

    def test_supersedes_different_artifact_is_valid(self) -> None:
        packet = build_packet(
            supersedes=ArtifactReference(
                artifact_id="urn:uuid:00000000-0000-0000-0000-000000000099",
                content_digest="sha256:" + "9" * 64,
            )
        )
        assert packet.supersedes is not None
        assert packet.supersedes.artifact_id.endswith("099")

    def test_rejects_supersedes_self(self) -> None:
        own_id = "urn:uuid:00000000-0000-0000-0000-000000000001"
        with pytest.raises(ValidationError, match="supersedes"):
            build_packet(
                artifact_id=own_id,
                supersedes=ArtifactReference(
                    artifact_id=own_id, content_digest="sha256:" + "9" * 64
                ),
            )


class TestPacketCanonicalizationDeterminism:
    def test_same_content_different_field_order_canonicalizes_identically(self) -> None:
        from zadc.canonical import canonical_json_text

        p1 = build_packet()
        p2 = Packet(
            **{
                **{k: v for k, v in p1.model_dump(mode="python", by_alias=True).items()},
            }
        )
        assert canonical_json_text(p1) == canonical_json_text(p2)
