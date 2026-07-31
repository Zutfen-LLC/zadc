"""Shared factory helpers for constructing valid A2A artifact instances.

Not a test module itself (no ``test_`` prefix) — imported by the A2A test
suite to avoid duplicating minimal-valid-instance boilerplate across every
invariant test.
"""

from datetime import UTC, datetime

from zadc import CONTRACT_VERSION, SCHEMA_ID, PolicyReference, ProducerIdentity, Provenance
from zadc.models.certification_manifest import CertificationManifest, LaneResult
from zadc.models.completion_report import (
    Changes,
    CompletionReport,
    DependencyPinResolution,
    RepositoryState,
    VerificationClaims,
    WorkStartObservation,
)
from zadc.models.evidence_artifact import EvidenceArtifact
from zadc.models.observation import Observation
from zadc.models.packet import (
    DependencyPin,
    Packet,
    PacketAuthorization,
    PacketIntent,
    PacketReview,
    PacketScope,
    RepositoryTarget,
    Requirement,
    VerificationRequirements,
    WorkStartAuthorization,
)
from zadc.models.shared import (
    EvidenceReference,
    ExactSubject,
    ExecutorClaim,
    ObservationSource,
    VerificationEnvironment,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64


def _producer() -> ProducerIdentity:
    return ProducerIdentity(actor_type="human", actor_id="zutfen:human:eric")


def _policy() -> PolicyReference:
    return PolicyReference(
        policy_id="zutfen:zadc-policy:standard@0.1.0",
        policy_source_sha=SHA_A,
        policy_digest=DIGEST_B,
    )


def _envelope_kwargs(artifact_type: str, artifact_id: str) -> dict[str, object]:
    return {
        "schema": SCHEMA_ID,
        "contract_version": CONTRACT_VERSION,
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "created_at": datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
        "producer": _producer(),
        "project_id": "zutfen:project:zadc",
        "slice_id": "ZADC-001A2A",
        "slice_instance_id": "ZADC-001A2A1",
        "policy": _policy(),
        "provenance": Provenance(parent_artifact_ids=()),
    }


def build_packet(**overrides: object) -> Packet:
    kwargs = _envelope_kwargs("packet", "urn:uuid:00000000-0000-0000-0000-000000000001")
    kwargs.update(
        {
            "authorization": PacketAuthorization(
                authorized_by="zutfen:human:eric",
                authorized_at=datetime(2026, 7, 31, 11, 0, 0, tzinfo=UTC),
            ),
            "repository": RepositoryTarget(
                repository_id="github:Zutfen-LLC/zadc",
                provider="github",
                owner="Zutfen-LLC",
                name="zadc",
                pull_request=42,
            ),
            "work_start": WorkStartAuthorization(expected_sha=SHA_A, mismatch_policy="abort"),
            "intent": PacketIntent(
                problem_statement="Implement A2A artifacts",
                desired_outcome="Concrete artifact models exist",
            ),
            "scope": PacketScope(
                allowed_paths=("src/zadc/**",),
                prohibited_paths=(".github/**",),
                allowed_operations=("edit",),
                prohibited_operations=("force_push",),
            ),
            "requirements": (
                Requirement(
                    requirement_id="REQ-1",
                    statement="Implement the five artifacts",
                    acceptance_criteria=("all tests pass",),
                ),
            ),
            "dependency_pins": (
                DependencyPin(
                    repository_id="github:Zutfen-LLC/engram",
                    sha=SHA_B,
                    cleanliness_required=True,
                ),
            ),
            "verification": VerificationRequirements(
                mandatory_lanes=("lint", "test"),
                advisory_lanes=("bench",),
                exact_subject_policy="final_pr_head",
                synthetic_merge_required=False,
            ),
            "review": PacketReview(
                independent_review_required=True, minimum_severity_blocking="blocker"
            ),
            "stop_conditions": ("stop if scope exceeded",),
            "deliverables": ("draft PR",),
            "completion_report_requirements": ("completion report required",),
            "supersedes": None,
        }
    )
    kwargs.update(overrides)
    return Packet(**kwargs)  # type: ignore[arg-type]


def build_completion_report(**overrides: object) -> CompletionReport:
    kwargs = _envelope_kwargs("completion_report", "urn:uuid:00000000-0000-0000-0000-000000000002")
    kwargs.update(
        {
            "packet_id": "urn:uuid:00000000-0000-0000-0000-000000000001",
            "run_id": "urn:uuid:00000000-0000-0000-0000-000000000003",
            "work_start": WorkStartObservation(expected_sha=SHA_A, actual_sha=SHA_A, match=True),
            "repository_state": RepositoryState(
                repository_id="github:Zutfen-LLC/zadc",
                base_sha=SHA_A,
                implementation_sha=SHA_B,
                pr_head_sha_observed=SHA_B,
                branch="feat/zadc-001a2a",
            ),
            "changes": Changes(
                commits=(SHA_B,),
                files_changed=("src/zadc/models/packet.py",),
                dependency_pins_resolved=(
                    DependencyPinResolution(
                        repository_id="github:Zutfen-LLC/engram", sha=SHA_C, clean=True
                    ),
                ),
            ),
            "verification_claims": VerificationClaims(
                commands_run=("make check",),
                local_results=(ExecutorClaim(statement="all tests passed", evidence_refs=()),),
            ),
            "deviations": (),
            "known_limitations": (
                ExecutorClaim(statement="lifecycle derivation is out of scope", evidence_refs=()),
            ),
            "open_issues": (),
            "executor_recommendation": "green_for_review",
        }
    )
    kwargs.update(overrides)
    return CompletionReport(**kwargs)  # type: ignore[arg-type]


def build_certification_manifest(**overrides: object) -> CertificationManifest:
    kwargs = _envelope_kwargs(
        "certification_manifest", "urn:uuid:00000000-0000-0000-0000-000000000004"
    )
    kwargs.update(
        {
            "packet_id": "urn:uuid:00000000-0000-0000-0000-000000000001",
            "run_id": "urn:uuid:00000000-0000-0000-0000-000000000005",
            "subject": ExactSubject(
                repository_id="github:Zutfen-LLC/zadc",
                subject_kind="pr_head",
                subject_sha=SHA_B,
                head_sha=SHA_B,
            ),
            "environment": VerificationEnvironment(
                runner_identity="github:actions-runner:ubuntu-latest",
                os="ubuntu-24.04",
                architecture="x86_64",
                toolchain=("python-3.13.12", "uv-0.8.13"),
                container_digests=(),
            ),
            "lanes": (
                LaneResult(
                    lane_id="test",
                    classification="mandatory",
                    conclusion="pass",
                    started_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
                    completed_at=datetime(2026, 7, 31, 12, 5, 0, tzinfo=UTC),
                    command_or_workflow="make check",
                    evidence_refs=(),
                ),
            ),
            "evidence": (
                EvidenceReference(
                    artifact_id="urn:uuid:00000000-0000-0000-0000-000000000006",
                    media_type="text/plain",
                    digest=DIGEST_C,
                    location="https://ci.example.com/artifacts/log.txt",
                ),
            ),
            "result": "pass",
        }
    )
    kwargs.update(overrides)
    return CertificationManifest(**kwargs)  # type: ignore[arg-type]


def build_evidence_artifact(**overrides: object) -> EvidenceArtifact:
    kwargs = _envelope_kwargs("evidence_artifact", "urn:uuid:00000000-0000-0000-0000-000000000007")
    kwargs.update(
        {
            "verification_run_id": "urn:uuid:00000000-0000-0000-0000-000000000005",
            "subject": ExactSubject(
                repository_id="github:Zutfen-LLC/zadc",
                subject_kind="commit",
                subject_sha=SHA_B,
            ),
            "media_type": "text/plain",
            "digest": DIGEST_C,
            "location": "https://ci.example.com/artifacts/log.txt",
            "availability": "available",
            "size_bytes": 1024,
            "description": "pytest coverage log",
        }
    )
    kwargs.update(overrides)
    return EvidenceArtifact(**kwargs)  # type: ignore[arg-type]


def build_observation(**overrides: object) -> Observation:
    kwargs = _envelope_kwargs("observation", "urn:uuid:00000000-0000-0000-0000-000000000008")
    kwargs.update(
        {
            "subject_id": "github:Zutfen-LLC/zadc/pull/42",
            "source": ObservationSource(
                source_type="github",
                source_id="github:Zutfen-LLC/zadc",
                source_event_id="evt-123",
            ),
            "observed_at": datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
            "statement": "PR #42 head SHA observed",
            "epistemic_status": "LIVE_SOURCE_OBSERVED",
            "evidence_refs": (),
            "freshness_seconds": 300,
            "expires_at": datetime(2026, 7, 31, 12, 10, 0, tzinfo=UTC),
        }
    )
    kwargs.update(overrides)
    return Observation(**kwargs)  # type: ignore[arg-type]


__all__ = [
    "SHA_A",
    "SHA_B",
    "SHA_C",
    "DIGEST_B",
    "DIGEST_C",
    "build_packet",
    "build_completion_report",
    "build_certification_manifest",
    "build_evidence_artifact",
    "build_observation",
]
