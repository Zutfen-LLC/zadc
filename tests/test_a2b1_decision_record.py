"""A2B1: the DecisionRecord artifact and its supporting models."""

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tests.a2b1_factories import (
    DECISION_RECORD_ID,
    DIGEST_C,
    HUMAN_DECIDER_ID,
    REVIEW_REPORT_ID,
    SHA_B,
    build_decision_record,
)
from zadc.canonical import canonical_json_text
from zadc.digests import compute_content_digest, seal_artifact, verify_content_digest
from zadc.errors import DigestMismatchError
from zadc.models.decision_record import (
    AcceptedRisk,
    DecisionRecord,
    DecisionSubject,
    HumanDecisionIdentity,
)
from zadc.models.shared import ArtifactReference


class TestDecisionRecordConstruction:
    def test_valid_decision_record(self) -> None:
        decision = build_decision_record()
        assert decision.artifact_type == "decision_record"
        assert decision.decision == "approve_for_merge"

    def test_rejects_wrong_artifact_type(self) -> None:
        with pytest.raises(ValidationError):
            build_decision_record(artifact_type="review_report")

    def test_rejects_extra_top_level_field(self) -> None:
        with pytest.raises(ValidationError):
            build_decision_record(unexpected_field="nope")

    def test_frozen(self) -> None:
        decision = build_decision_record()
        with pytest.raises(ValidationError):
            decision.artifact_id = "urn:uuid:00000000-0000-0000-0000-000000000999"

    def test_list_and_tuple_inputs_are_equivalent(self) -> None:
        as_list = build_decision_record(conditions=["a", "b"])
        as_tuple = build_decision_record(conditions=("a", "b"))
        assert as_list.conditions == as_tuple.conditions == ("a", "b")
        assert isinstance(as_list.conditions, tuple)

    def test_decision_id_must_equal_artifact_id(self) -> None:
        with pytest.raises(ValidationError, match="decision_id"):
            build_decision_record(decision_id="urn:uuid:00000000-0000-0000-0000-000000000999")

    def test_producer_must_be_human(self) -> None:
        from zadc import ProducerIdentity

        with pytest.raises(ValidationError, match="human"):
            build_decision_record(
                producer=ProducerIdentity(actor_type="agent", actor_id=HUMAN_DECIDER_ID)
            )

    def test_producer_actor_id_must_match_decided_by(self) -> None:
        from zadc import ProducerIdentity

        with pytest.raises(ValidationError, match="human"):
            build_decision_record(
                producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:someone-else")
            )


class TestHumanDecisionIdentity:
    def test_rejects_non_human_actor_type(self) -> None:
        with pytest.raises(ValidationError):
            HumanDecisionIdentity(actor_type="agent", actor_id="zutfen:agent:claude")  # type: ignore[arg-type]


class TestDecisionSubject:
    def _kwargs(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "repository_id": "github:Zutfen-LLC/zadc",
            "pull_request": 42,
            "decision_subject_sha": SHA_B,
            "current_pr_head_sha_observed": SHA_B,
            "review_report_ids": (REVIEW_REPORT_ID,),
            "certification_manifest_ids": (),
        }
        base.update(overrides)
        return base

    def test_valid(self) -> None:
        subject = DecisionSubject(**self._kwargs())  # type: ignore[arg-type]
        assert subject.pull_request == 42

    def test_subject_sha_and_observed_head_may_differ(self) -> None:
        subject = DecisionSubject(
            **self._kwargs(current_pr_head_sha_observed="c" * 40)  # type: ignore[arg-type]
        )
        assert subject.decision_subject_sha != subject.current_pr_head_sha_observed

    def test_duplicate_review_report_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match="review_report_ids"):
            DecisionSubject(
                **self._kwargs(review_report_ids=(REVIEW_REPORT_ID, REVIEW_REPORT_ID))  # type: ignore[arg-type]
            )

    def test_duplicate_certification_manifest_ids_rejected(self) -> None:
        manifest_id = "urn:uuid:00000000-0000-0000-0000-000000000006"
        with pytest.raises(ValidationError, match="certification_manifest_ids"):
            DecisionSubject(
                **self._kwargs(certification_manifest_ids=(manifest_id, manifest_id))  # type: ignore[arg-type]
            )


class TestDecisionGates:
    def test_accept_risk_requires_nonempty_accepted_risks(self) -> None:
        with pytest.raises(ValidationError, match="accept_risk"):
            build_decision_record(decision="accept_risk", accepted_risks=())

    def test_accept_risk_with_accepted_risk_accepted(self) -> None:
        decision = build_decision_record(
            decision="accept_risk",
            accepted_risks=(
                AcceptedRisk(finding_id="F-1", rationale="acceptable", scope="this PR only"),
            ),
        )
        assert decision.decision == "accept_risk"

    @pytest.mark.parametrize(
        "decision", ["request_changes", "approve_for_merge", "reject", "supersede"]
    )
    def test_non_accept_risk_rejects_nonempty_accepted_risks(self, decision: str) -> None:
        overrides: dict[str, object] = {
            "decision": decision,
            "accepted_risks": (AcceptedRisk(finding_id="F-1", rationale="x", scope="y"),),
        }
        if decision == "supersede":
            overrides["supersedes_decision_ref"] = ArtifactReference(
                artifact_id="urn:uuid:00000000-0000-0000-0000-000000000777",
                content_digest=DIGEST_C,
            )
        with pytest.raises(ValidationError, match="accepted_risks"):
            build_decision_record(**overrides)

    def test_supersede_requires_supersedes_decision_ref(self) -> None:
        with pytest.raises(ValidationError, match="supersede"):
            build_decision_record(decision="supersede", supersedes_decision_ref=None)

    def test_supersede_with_ref_accepted(self) -> None:
        decision = build_decision_record(
            decision="supersede",
            supersedes_decision_ref=ArtifactReference(
                artifact_id="urn:uuid:00000000-0000-0000-0000-000000000777",
                content_digest=DIGEST_C,
            ),
        )
        assert decision.decision == "supersede"

    @pytest.mark.parametrize(
        "decision", ["request_changes", "approve_for_merge", "reject", "accept_risk"]
    )
    def test_non_supersede_rejects_supersedes_decision_ref(self, decision: str) -> None:
        overrides: dict[str, object] = {
            "decision": decision,
            "supersedes_decision_ref": ArtifactReference(
                artifact_id="urn:uuid:00000000-0000-0000-0000-000000000777",
                content_digest=DIGEST_C,
            ),
        }
        if decision == "accept_risk":
            overrides["accepted_risks"] = (
                AcceptedRisk(finding_id="F-1", rationale="x", scope="y"),
            )
        with pytest.raises(ValidationError, match="supersedes_decision_ref"):
            build_decision_record(**overrides)

    def test_supersedes_decision_ref_cannot_self_reference(self) -> None:
        with pytest.raises(ValidationError, match="supersedes_decision_ref"):
            build_decision_record(
                decision="supersede",
                supersedes_decision_ref=ArtifactReference(
                    artifact_id=DECISION_RECORD_ID, content_digest=DIGEST_C
                ),
            )

    def test_duplicate_accepted_risk_finding_ids_rejected(self) -> None:
        risk = AcceptedRisk(finding_id="F-DUP", rationale="x", scope="y")
        with pytest.raises(ValidationError, match="unique"):
            build_decision_record(decision="accept_risk", accepted_risks=(risk, risk))

    def test_accepted_risk_expires_at_must_be_later_than_decided_at(self) -> None:
        decided_at = datetime(2026, 7, 31, 13, 0, 0, tzinfo=UTC)
        risk = AcceptedRisk(
            finding_id="F-1",
            rationale="x",
            scope="y",
            expires_at=decided_at,
        )
        with pytest.raises(ValidationError, match="expires_at"):
            build_decision_record(
                decision="accept_risk", decided_at=decided_at, accepted_risks=(risk,)
            )

    def test_accepted_risk_expires_at_after_decided_at_accepted(self) -> None:
        decided_at = datetime(2026, 7, 31, 13, 0, 0, tzinfo=UTC)
        risk = AcceptedRisk(
            finding_id="F-1",
            rationale="x",
            scope="y",
            expires_at=datetime(2026, 8, 1, 13, 0, 0, tzinfo=UTC),
        )
        decision = build_decision_record(
            decision="accept_risk", decided_at=decided_at, accepted_risks=(risk,)
        )
        assert decision.accepted_risks[0].expires_at is not None

    def test_accepted_risk_without_expires_at_allowed(self) -> None:
        risk = AcceptedRisk(finding_id="F-1", rationale="x", scope="y")
        decision = build_decision_record(decision="accept_risk", accepted_risks=(risk,))
        assert decision.accepted_risks[0].expires_at is None


class TestDecisionRecordDigestSealingAndCanonicalization:
    def test_seal_preserves_concrete_class(self) -> None:
        decision = build_decision_record()
        sealed = seal_artifact(decision)
        assert type(sealed) is DecisionRecord
        assert sealed.provenance.content_digest is not None

    def test_verify_content_digest_roundtrip(self) -> None:
        sealed = seal_artifact(build_decision_record())
        verify_content_digest(sealed)

    def test_tamper_top_level_field_detected(self) -> None:
        sealed = seal_artifact(build_decision_record())
        data = json.loads(canonical_json_text(sealed))
        data["rationale"] = "a different rationale entirely"
        tampered = DecisionRecord.model_validate(data)
        with pytest.raises(DigestMismatchError):
            verify_content_digest(tampered)

    def test_tamper_nested_field_detected(self) -> None:
        sealed = seal_artifact(build_decision_record())
        data = json.loads(canonical_json_text(sealed))
        data["subject"]["pull_request"] = 999
        tampered = DecisionRecord.model_validate(data)
        with pytest.raises(DigestMismatchError):
            verify_content_digest(tampered)

    def test_canonical_round_trip_reload(self) -> None:
        sealed = seal_artifact(build_decision_record())
        data = json.loads(canonical_json_text(sealed))
        reloaded = DecisionRecord.model_validate(data)
        assert reloaded == sealed
        verify_content_digest(reloaded)

    def test_canonical_output_invariant_across_list_and_tuple_input(self) -> None:
        as_list = build_decision_record(conditions=["one condition"])
        as_tuple = build_decision_record(conditions=("one condition",))
        assert compute_content_digest(as_list) == compute_content_digest(as_tuple)

    def test_canonical_output_invariant_across_field_order(self) -> None:
        decision = build_decision_record()
        kwargs = decision.model_dump(mode="python", by_alias=True)
        reordered_kwargs = dict(reversed(list(kwargs.items())))
        reordered = DecisionRecord.model_validate(reordered_kwargs)
        assert compute_content_digest(decision) == compute_content_digest(reordered)
