"""Shared factory helpers for constructing valid A2B2 WorkflowBundle instances.

Not a test module itself (no ``test_`` prefix) — imported by the A2B2 test
suite. Reuses the A2A and A2B1 factory builders to construct the seven
non-bundle artifacts a :class:`~zadc.models.workflow_bundle.WorkflowBundle`
references, sealing each so real content digests back the bundle's typed
``ArtifactReference`` collections.
"""

from datetime import UTC, datetime

from tests.a2a_factories import (
    DIGEST_B,
    DIGEST_C,
    SHA_A,
    SHA_B,
    SHA_C,
    build_certification_manifest,
    build_completion_report,
    build_evidence_artifact,
    build_observation,
    build_packet,
)
from tests.a2b1_factories import build_decision_record, build_review_report
from zadc import CONTRACT_VERSION, SCHEMA_ID, PolicyReference, ProducerIdentity, Provenance
from zadc.digests import seal_artifact
from zadc.models.common import ArtifactEnvelope
from zadc.models.shared import ArtifactReference
from zadc.models.workflow_bundle import (
    AgentRunReference,
    BundleBlocker,
    DerivedStateSnapshot,
    WorkflowBundle,
)

VALIDATOR_ID = "zutfen:validator:zadc"
EXECUTOR_ID = "zutfen:agent:hermes"

WORKFLOW_BUNDLE_ID = "urn:uuid:00000000-0000-0000-0000-000000000301"
AGENT_RUN_ID = "urn:uuid:00000000-0000-0000-0000-000000000902"
VALIDATOR_RUN_ID = "urn:uuid:00000000-0000-0000-0000-000000000900"


def _validator_producer() -> ProducerIdentity:
    return ProducerIdentity(actor_type="validator", actor_id=VALIDATOR_ID)


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
        "created_at": datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
        "producer": _validator_producer(),
        "project_id": "zutfen:project:zadc",
        "slice_id": "ZADC-001A2B2",
        "slice_instance_id": "ZADC-001A2B21",
        "policy": _policy(),
        "provenance": Provenance(parent_artifact_ids=()),
    }


def sealed_ref(artifact: ArtifactEnvelope) -> ArtifactReference:
    """Seal an artifact and return an ArtifactReference pointing at it."""
    sealed = seal_artifact(artifact)
    digest = sealed.provenance.content_digest
    assert digest is not None
    return ArtifactReference(artifact_id=sealed.artifact_id, content_digest=digest)


def build_minimal_workflow_bundle(**overrides: object) -> WorkflowBundle:
    """The smallest structurally valid WorkflowBundle: one packet_ref, empty everything else."""
    packet_ref = sealed_ref(build_packet())
    derived_state = DerivedStateSnapshot(
        state="pending",
        computed_at=datetime(2026, 8, 1, 11, 30, 0, tzinfo=UTC),
        validator_actor_id=VALIDATOR_ID,
        validator_run_id=VALIDATOR_RUN_ID,
        policy=_policy(),
        input_artifact_refs=(),
        blockers=(),
        stale_artifact_refs=(),
        next_admissible_actions=(),
    )
    kwargs = _envelope_kwargs("workflow_bundle", WORKFLOW_BUNDLE_ID)
    kwargs.update(
        {
            "bundle_id": WORKFLOW_BUNDLE_ID,
            "packet_ref": packet_ref,
            "agent_run_refs": (),
            "completion_report_refs": (),
            "certification_manifest_refs": (),
            "evidence_artifact_refs": (),
            "review_report_refs": (),
            "decision_record_refs": (),
            "observation_refs": (),
            "supersedes_bundle_ref": None,
            "derived_state": derived_state,
        }
    )
    kwargs.update(overrides)
    return WorkflowBundle(**kwargs)  # type: ignore[arg-type]


def build_workflow_bundle(**overrides: object) -> WorkflowBundle:
    """A fully populated, structurally valid WorkflowBundle.

    References sealed instances of all seven other concrete artifacts, and
    a populated ``derived_state`` whose input/blocker/stale references are
    a subset of — and digest-consistent with — the bundle's top-level
    typed reference collections.
    """
    packet_ref = sealed_ref(build_packet())
    completion_ref = sealed_ref(build_completion_report())
    cert_ref = sealed_ref(build_certification_manifest())
    evidence_ref = sealed_ref(build_evidence_artifact())
    review_ref = sealed_ref(build_review_report())
    decision_ref = sealed_ref(build_decision_record())
    observation_ref = sealed_ref(build_observation())

    derived_state = DerivedStateSnapshot(
        state="awaiting_review",
        computed_at=datetime(2026, 8, 1, 11, 30, 0, tzinfo=UTC),
        validator_actor_id=VALIDATOR_ID,
        validator_run_id=VALIDATOR_RUN_ID,
        policy=_policy(),
        input_artifact_refs=(packet_ref, completion_ref),
        blockers=(
            BundleBlocker(
                blocker_id="B-1",
                code="missing-certification-pass",
                statement="Certification manifest has not reached a pass result",
                artifact_refs=(cert_ref,),
            ),
        ),
        stale_artifact_refs=(observation_ref,),
        next_admissible_actions=("submit_review", "request_changes"),
    )

    kwargs = _envelope_kwargs("workflow_bundle", WORKFLOW_BUNDLE_ID)
    kwargs.update(
        {
            "bundle_id": WORKFLOW_BUNDLE_ID,
            "packet_ref": packet_ref,
            "agent_run_refs": (
                AgentRunReference(
                    run_id=AGENT_RUN_ID,
                    executor_actor_id=EXECUTOR_ID,
                    framework="claude-code",
                    model="claude-sonnet-5",
                    provider="anthropic",
                ),
            ),
            "completion_report_refs": (completion_ref,),
            "certification_manifest_refs": (cert_ref,),
            "evidence_artifact_refs": (evidence_ref,),
            "review_report_refs": (review_ref,),
            "decision_record_refs": (decision_ref,),
            "observation_refs": (observation_ref,),
            "supersedes_bundle_ref": None,
            "derived_state": derived_state,
        }
    )
    kwargs.update(overrides)
    return WorkflowBundle(**kwargs)  # type: ignore[arg-type]


__all__ = [
    "VALIDATOR_ID",
    "EXECUTOR_ID",
    "WORKFLOW_BUNDLE_ID",
    "AGENT_RUN_ID",
    "VALIDATOR_RUN_ID",
    "SHA_A",
    "SHA_B",
    "SHA_C",
    "DIGEST_B",
    "DIGEST_C",
    "sealed_ref",
    "build_minimal_workflow_bundle",
    "build_workflow_bundle",
]
