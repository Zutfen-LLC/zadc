"""A2B2: clean-venv wheel smoke test covering WorkflowBundle and ZadcArtifact.

Constructs, seals, canonicalizes, reloads, and verifies a WorkflowBundle
(referencing sealed instances of all seven other concrete artifacts) from a
clean virtual environment with only the built wheel installed, then proves
the global ``ZadcArtifact`` union dispatches all eight variants to their
exact concrete class — mirroring ``tests/test_a2b1_package_smoke.py``.
"""

import glob
import os
import subprocess
import sys
import tempfile

import pytest

_SMOKE_SCRIPT = r"""
import json
from datetime import datetime, timezone

import zadc

required_names = [
    "WorkflowBundle", "AgentRunReference", "BundleBlocker", "DerivedStateSnapshot",
    "ZadcArtifact", "ZADC_ARTIFACT_ADAPTER", "validate_artifact", "validate_artifact_json",
]
for name in required_names:
    assert hasattr(zadc, name), f"zadc is missing public name: {name}"

SHA_A = "a" * 40
SHA_B = "b" * 40
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64

human_producer = zadc.ProducerIdentity(actor_type="human", actor_id="zutfen:human:smoke")
validator_producer = zadc.ProducerIdentity(
    actor_type="validator", actor_id="zutfen:validator:smoke"
)
policy = zadc.PolicyReference(
    policy_id="zutfen:zadc-policy:standard@0.1.0",
    policy_source_sha=SHA_A,
    policy_digest=DIGEST_B,
)


def envelope_kwargs(artifact_type, artifact_id, producer=human_producer):
    return dict(
        schema=zadc.SCHEMA_ID,
        contract_version=zadc.CONTRACT_VERSION,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        created_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
        producer=producer,
        project_id="zutfen:project:zadc",
        slice_id="SMOKE-001A2B2",
        slice_instance_id="SMOKE-001A2B21",
        policy=policy,
        provenance=zadc.Provenance(parent_artifact_ids=()),
    )


def sealed_ref(artifact):
    sealed = zadc.seal_artifact(artifact)
    return zadc.ArtifactReference(
        artifact_id=sealed.artifact_id, content_digest=sealed.provenance.content_digest
    )


packet = zadc.Packet(
    **envelope_kwargs("packet", "urn:uuid:00000000-0000-0000-0000-000000000401"),
    authorization=zadc.PacketAuthorization(
        authorized_by="zutfen:human:smoke",
        authorized_at=datetime(2026, 8, 1, 11, 0, 0, tzinfo=timezone.utc),
    ),
    repository=zadc.RepositoryTarget(
        repository_id="github:Zutfen-LLC/zadc", provider="github", owner="Zutfen-LLC", name="zadc"
    ),
    work_start=zadc.WorkStartAuthorization(expected_sha=SHA_A, mismatch_policy="abort"),
    intent=zadc.PacketIntent(problem_statement="smoke", desired_outcome="smoke ok"),
    scope=zadc.PacketScope(
        allowed_paths=[], prohibited_paths=[], allowed_operations=[], prohibited_operations=[]
    ),
    requirements=[], dependency_pins=[],
    verification=zadc.VerificationRequirements(
        mandatory_lanes=[], advisory_lanes=[], exact_subject_policy="final_pr_head",
        synthetic_merge_required=False,
    ),
    review=zadc.PacketReview(independent_review_required=True, minimum_severity_blocking="blocker"),
    stop_conditions=[], deliverables=[], completion_report_requirements=[], supersedes=None,
)

completion_report = zadc.CompletionReport(
    **envelope_kwargs("completion_report", "urn:uuid:00000000-0000-0000-0000-000000000402"),
    packet_id=packet.artifact_id,
    run_id="urn:uuid:00000000-0000-0000-0000-000000000403",
    work_start=zadc.WorkStartObservation(expected_sha=SHA_A, actual_sha=SHA_A, match=True),
    repository_state=zadc.RepositoryState(
        repository_id="github:Zutfen-LLC/zadc", base_sha=SHA_A, implementation_sha=SHA_B,
        branch="main",
    ),
    changes=zadc.Changes(commits=[], files_changed=[], dependency_pins_resolved=[]),
    verification_claims=zadc.VerificationClaims(commands_run=[], local_results=[]),
    deviations=[], known_limitations=[], open_issues=[],
    executor_recommendation="green_for_review",
)

certification_manifest = zadc.CertificationManifest(
    **envelope_kwargs("certification_manifest", "urn:uuid:00000000-0000-0000-0000-000000000404"),
    packet_id=packet.artifact_id,
    run_id="urn:uuid:00000000-0000-0000-0000-000000000405",
    subject=zadc.ExactSubject(
        repository_id="github:Zutfen-LLC/zadc", subject_kind="commit", subject_sha=SHA_B
    ),
    environment=zadc.VerificationEnvironment(
        runner_identity="github:actions-runner:ubuntu-latest", os="ubuntu-24.04",
        architecture="x86_64", toolchain=[], container_digests=[],
    ),
    lanes=[], evidence=[], result="inconclusive",
)

evidence_artifact = zadc.EvidenceArtifact(
    **envelope_kwargs("evidence_artifact", "urn:uuid:00000000-0000-0000-0000-000000000406"),
    verification_run_id="urn:uuid:00000000-0000-0000-0000-000000000405",
    subject=zadc.ExactSubject(
        repository_id="github:Zutfen-LLC/zadc", subject_kind="commit", subject_sha=SHA_B
    ),
    media_type="text/plain", digest=DIGEST_C,
    location="https://ci.example.com/log.txt", availability="available",
    size_bytes=None, description="smoke evidence",
)

observation = zadc.Observation(
    **envelope_kwargs("observation", "urn:uuid:00000000-0000-0000-0000-000000000407"),
    subject_id="github:Zutfen-LLC/zadc/pull/1",
    source=zadc.ObservationSource(source_type="github", source_id="github:Zutfen-LLC/zadc"),
    observed_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
    statement="smoke observed", epistemic_status="AGENT_REPORTED", evidence_refs=[],
    freshness_seconds=None, expires_at=None,
)

review_report = zadc.ReviewReport(
    **envelope_kwargs("review_report", "urn:uuid:00000000-0000-0000-0000-000000000408"),
    packet_id=packet.artifact_id,
    review_id="urn:uuid:00000000-0000-0000-0000-000000000408",
    reviewer=zadc.ReviewerIdentity(actor_type="human", actor_id="zutfen:human:smoke"),
    independence=zadc.ReviewIndependence(executor_actor_id="zutfen:agent:hermes", satisfied=True),
    subject=zadc.ReviewSubject(
        repository_id="github:Zutfen-LLC/zadc", review_subject_sha=SHA_B,
        packet_digest=DIGEST_C, certification_manifest_ids=[],
    ),
    inputs_reviewed=zadc.ReviewInputs(diffs=[], files=[], evidence_artifacts=[]),
    findings=[], limitations=[], reviewer_recommendation="green_for_review",
)

decision_record = zadc.DecisionRecord(
    **envelope_kwargs("decision_record", "urn:uuid:00000000-0000-0000-0000-000000000409"),
    decision_id="urn:uuid:00000000-0000-0000-0000-000000000409",
    decided_by=zadc.HumanDecisionIdentity(actor_type="human", actor_id="zutfen:human:smoke"),
    decided_at=datetime(2026, 8, 1, 13, 0, 0, tzinfo=timezone.utc),
    subject=zadc.DecisionSubject(
        repository_id="github:Zutfen-LLC/zadc", pull_request=1,
        decision_subject_sha=SHA_B, current_pr_head_sha_observed=SHA_B,
        review_report_ids=[review_report.artifact_id], certification_manifest_ids=[],
    ),
    decision="approve_for_merge",
    accepted_risks=[], supersedes_decision_ref=None,
    conditions=[], rationale="smoke approval",
)

bundle_id = "urn:uuid:00000000-0000-0000-0000-000000000410"
derived_state = zadc.DerivedStateSnapshot(
    state="awaiting_review",
    computed_at=datetime(2026, 8, 1, 12, 30, 0, tzinfo=timezone.utc),
    validator_actor_id="zutfen:validator:smoke",
    validator_run_id="urn:uuid:00000000-0000-0000-0000-000000000901",
    policy=policy,
    input_artifact_refs=[sealed_ref(packet)],
    blockers=[],
    stale_artifact_refs=[],
    next_admissible_actions=["submit_review"],
)

workflow_bundle = zadc.WorkflowBundle(
    **envelope_kwargs("workflow_bundle", bundle_id, producer=validator_producer),
    bundle_id=bundle_id,
    packet_ref=sealed_ref(packet),
    agent_run_refs=[
        zadc.AgentRunReference(
            run_id="urn:uuid:00000000-0000-0000-0000-000000000902",
            executor_actor_id="zutfen:agent:hermes",
        )
    ],
    completion_report_refs=[sealed_ref(completion_report)],
    certification_manifest_refs=[sealed_ref(certification_manifest)],
    evidence_artifact_refs=[sealed_ref(evidence_artifact)],
    review_report_refs=[sealed_ref(review_report)],
    decision_record_refs=[sealed_ref(decision_record)],
    observation_refs=[sealed_ref(observation)],
    supersedes_bundle_ref=None,
    derived_state=derived_state,
)

all_artifacts = [
    packet, completion_report, certification_manifest, evidence_artifact,
    observation, review_report, decision_record, workflow_bundle,
]

for artifact in all_artifacts:
    sealed = zadc.seal_artifact(artifact)
    assert type(sealed) is type(artifact)
    assert sealed.provenance.content_digest is not None
    data = json.loads(zadc.canonical_json_text(sealed))
    reloaded = type(sealed).model_validate(data)
    zadc.verify_content_digest(reloaded)

    union_reloaded = zadc.validate_artifact(data)
    assert type(union_reloaded) is type(artifact)
    zadc.verify_content_digest(union_reloaded)

    text = zadc.canonical_json_text(sealed)
    union_json_reloaded = zadc.validate_artifact_json(text)
    assert type(union_json_reloaded) is type(artifact)

print("A2B2_SMOKE_OK")
"""


@pytest.fixture
def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestA2B2PackageSmokeCleanVenv:
    """Clean-venv wheel smoke covering WorkflowBundle and ZadcArtifact."""

    def test_wheel_workflow_bundle_and_union_construct_seal_verify(self, repo_root: str) -> None:
        dist_dir = os.path.join(repo_root, "dist")
        wheels = glob.glob(os.path.join(dist_dir, "*.whl"))
        if not wheels:
            pytest.skip("dist/ not built yet — run 'make build' first")

        wheel = wheels[0]
        python = sys.executable

        with tempfile.TemporaryDirectory(prefix="zadc-a2b2-smoke-") as tmpdir:
            venv_dir = os.path.join(tmpdir, "venv")
            venv_python = os.path.join(venv_dir, "bin", "python")

            result = subprocess.run(
                [python, "-m", "venv", venv_dir], capture_output=True, text=True
            )
            assert result.returncode == 0

            result = subprocess.run(
                [venv_python, "-m", "pip", "install", wheel], capture_output=True, text=True
            )
            assert result.returncode == 0, f"pip install failed: {result.stderr}"

            script_path = os.path.join(tmpdir, "a2b2_smoke.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(_SMOKE_SCRIPT)

            result = subprocess.run([venv_python, script_path], capture_output=True, text=True)
            assert result.returncode == 0, (
                f"A2B2 smoke test failed: {result.stderr}\nstdout: {result.stdout}"
            )
            assert "A2B2_SMOKE_OK" in result.stdout
