"""Shared factory helpers for constructing valid A2B1 artifact instances.

Not a test module itself (no ``test_`` prefix) — imported by the A2B1 test
suite to avoid duplicating minimal-valid-instance boilerplate across every
invariant test. Reuses the SHA/digest constants from
:mod:`tests.a2a_factories` rather than redefining them.
"""

from datetime import UTC, datetime

from tests.a2a_factories import DIGEST_B, DIGEST_C, SHA_A, SHA_B, SHA_C
from zadc import CONTRACT_VERSION, SCHEMA_ID, PolicyReference, ProducerIdentity, Provenance
from zadc.models.decision_record import (
    DecisionRecord,
    DecisionSubject,
    HumanDecisionIdentity,
)
from zadc.models.review_report import (
    FileFindingLocation,
    Finding,
    ReviewedFile,
    ReviewerIdentity,
    ReviewIndependence,
    ReviewInputs,
    ReviewReport,
    ReviewSubject,
)
from zadc.models.shared import ArtifactReference

REVIEWER_ID = "zutfen:human:reviewer"
EXECUTOR_ID = "zutfen:agent:hermes"
HUMAN_DECIDER_ID = "zutfen:human:decider"

REVIEW_REPORT_ID = "urn:uuid:00000000-0000-0000-0000-000000000201"
DECISION_RECORD_ID = "urn:uuid:00000000-0000-0000-0000-000000000202"
PACKET_ID = "urn:uuid:00000000-0000-0000-0000-000000000001"


def _human_producer(actor_id: str) -> ProducerIdentity:
    return ProducerIdentity(actor_type="human", actor_id=actor_id)


def _policy() -> PolicyReference:
    return PolicyReference(
        policy_id="zutfen:zadc-policy:standard@0.1.0",
        policy_source_sha=SHA_A,
        policy_digest=DIGEST_B,
    )


def _envelope_kwargs(
    artifact_type: str, artifact_id: str, producer: ProducerIdentity
) -> dict[str, object]:
    return {
        "schema": SCHEMA_ID,
        "contract_version": CONTRACT_VERSION,
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "created_at": datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
        "producer": producer,
        "project_id": "zutfen:project:zadc",
        "slice_id": "ZADC-001A2B1",
        "slice_instance_id": "ZADC-001A2B11",
        "policy": _policy(),
        "provenance": Provenance(parent_artifact_ids=()),
    }


def build_review_report(**overrides: object) -> ReviewReport:
    kwargs = _envelope_kwargs("review_report", REVIEW_REPORT_ID, _human_producer(REVIEWER_ID))
    kwargs.update(
        {
            "packet_id": PACKET_ID,
            "review_id": REVIEW_REPORT_ID,
            "reviewer": ReviewerIdentity(actor_type="human", actor_id=REVIEWER_ID),
            "independence": ReviewIndependence(executor_actor_id=EXECUTOR_ID, satisfied=True),
            "subject": ReviewSubject(
                repository_id="github:Zutfen-LLC/zadc",
                review_subject_sha=SHA_B,
                packet_digest=DIGEST_C,
                certification_manifest_ids=("urn:uuid:00000000-0000-0000-0000-000000000006",),
            ),
            "inputs_reviewed": ReviewInputs(
                diffs=(),
                files=(ReviewedFile(path="src/zadc/models/packet.py", start_line=1, end_line=10),),
                evidence_artifacts=(),
            ),
            "findings": (
                Finding(
                    finding_id="F-1",
                    severity="minor",
                    status="open",
                    location=FileFindingLocation(
                        location_type="file", path="src/zadc/models/packet.py"
                    ),
                    statement="Minor style nit",
                    rationale="Not blocking",
                    resolution_refs=(),
                ),
            ),
            "limitations": ("Review was time-boxed to one hour",),
            "reviewer_recommendation": "green_for_review",
        }
    )
    kwargs.update(overrides)
    return ReviewReport(**kwargs)  # type: ignore[arg-type]


def build_decision_record(**overrides: object) -> DecisionRecord:
    kwargs = _envelope_kwargs(
        "decision_record", DECISION_RECORD_ID, _human_producer(HUMAN_DECIDER_ID)
    )
    kwargs.update(
        {
            "decision_id": DECISION_RECORD_ID,
            "decided_by": HumanDecisionIdentity(actor_type="human", actor_id=HUMAN_DECIDER_ID),
            "decided_at": datetime(2026, 7, 31, 13, 0, 0, tzinfo=UTC),
            "subject": DecisionSubject(
                repository_id="github:Zutfen-LLC/zadc",
                pull_request=42,
                decision_subject_sha=SHA_B,
                current_pr_head_sha_observed=SHA_B,
                review_report_ids=(REVIEW_REPORT_ID,),
                certification_manifest_ids=("urn:uuid:00000000-0000-0000-0000-000000000006",),
            ),
            "decision": "approve_for_merge",
            "accepted_risks": (),
            "supersedes_decision_ref": None,
            "conditions": (),
            "rationale": "All mandatory lanes passed and findings are non-blocking",
        }
    )
    kwargs.update(overrides)
    return DecisionRecord(**kwargs)  # type: ignore[arg-type]


__all__ = [
    "REVIEWER_ID",
    "EXECUTOR_ID",
    "HUMAN_DECIDER_ID",
    "REVIEW_REPORT_ID",
    "DECISION_RECORD_ID",
    "PACKET_ID",
    "SHA_A",
    "SHA_B",
    "SHA_C",
    "DIGEST_B",
    "DIGEST_C",
    "ArtifactReference",
    "build_review_report",
    "build_decision_record",
]
