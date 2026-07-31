"""A2A: clean-venv wheel smoke test covering all five concrete artifacts.

Constructs, seals, canonicalizes, reloads, and verifies a Packet,
CompletionReport, CertificationManifest, EvidenceArtifact, and Observation
from a clean virtual environment with only the built wheel installed.
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
    "Packet", "PacketAuthorization", "RepositoryTarget", "WorkStartAuthorization",
    "PacketIntent", "PacketScope", "Requirement", "DependencyPin",
    "VerificationRequirements", "PacketReview",
    "CompletionReport", "ReconciliationCommit", "Reconciliation",
    "WorkStartObservation", "RepositoryState", "DependencyPinResolution",
    "Changes", "VerificationClaims",
    "CertificationManifest", "LaneResult",
    "EvidenceArtifact",
    "Observation",
    "ArtifactReference", "EvidenceReference", "ExactSubject",
    "VerificationEnvironment", "ObservationSource", "ExecutorClaim",
    "Timestamp", "ConstrainedText", "StableId", "MediaType", "GitHubName", "RefName",
]
for name in required_names:
    assert hasattr(zadc, name), f"zadc is missing public name: {name}"

SHA_A = "a" * 40
SHA_B = "b" * 40
DIGEST = "sha256:" + "c" * 64

producer = zadc.ProducerIdentity(actor_type="human", actor_id="zutfen:human:smoke")
policy = zadc.PolicyReference(
    policy_id="zutfen:zadc-policy:standard@0.1.0",
    policy_source_sha=SHA_A,
    policy_digest="sha256:" + "b" * 64,
)


def envelope_kwargs(artifact_type, artifact_id):
    return dict(
        schema=zadc.SCHEMA_ID,
        contract_version=zadc.CONTRACT_VERSION,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc),
        producer=producer,
        project_id="zutfen:project:zadc",
        slice_id="SMOKE-001A2A",
        slice_instance_id="SMOKE-001A2A1",
        policy=policy,
        provenance=zadc.Provenance(parent_artifact_ids=()),
    )


packet = zadc.Packet(
    **envelope_kwargs("packet", "urn:uuid:00000000-0000-0000-0000-000000000101"),
    authorization=zadc.PacketAuthorization(
        authorized_by="zutfen:human:smoke",
        authorized_at=datetime(2026, 7, 31, 11, 0, 0, tzinfo=timezone.utc),
    ),
    repository=zadc.RepositoryTarget(
        repository_id="github:Zutfen-LLC/zadc", provider="github", owner="Zutfen-LLC", name="zadc"
    ),
    work_start=zadc.WorkStartAuthorization(expected_sha=SHA_A, mismatch_policy="abort"),
    intent=zadc.PacketIntent(problem_statement="smoke", desired_outcome="smoke ok"),
    scope=zadc.PacketScope(
        allowed_paths=[], prohibited_paths=[], allowed_operations=[], prohibited_operations=[]
    ),
    requirements=[],
    dependency_pins=[],
    verification=zadc.VerificationRequirements(
        mandatory_lanes=[], advisory_lanes=[], exact_subject_policy="final_pr_head",
        synthetic_merge_required=False,
    ),
    review=zadc.PacketReview(independent_review_required=True, minimum_severity_blocking="blocker"),
    stop_conditions=[], deliverables=[], completion_report_requirements=[], supersedes=None,
)

completion_report = zadc.CompletionReport(
    **envelope_kwargs("completion_report", "urn:uuid:00000000-0000-0000-0000-000000000102"),
    packet_id=packet.artifact_id,
    run_id="urn:uuid:00000000-0000-0000-0000-000000000103",
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
    **envelope_kwargs("certification_manifest", "urn:uuid:00000000-0000-0000-0000-000000000104"),
    packet_id=packet.artifact_id,
    run_id="urn:uuid:00000000-0000-0000-0000-000000000105",
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
    **envelope_kwargs("evidence_artifact", "urn:uuid:00000000-0000-0000-0000-000000000106"),
    verification_run_id="urn:uuid:00000000-0000-0000-0000-000000000105",
    subject=zadc.ExactSubject(
        repository_id="github:Zutfen-LLC/zadc", subject_kind="commit", subject_sha=SHA_B
    ),
    media_type="text/plain", digest=DIGEST,
    location="https://ci.example.com/log.txt", availability="available",
    size_bytes=None, description="smoke evidence",
)

observation = zadc.Observation(
    **envelope_kwargs("observation", "urn:uuid:00000000-0000-0000-0000-000000000107"),
    subject_id="github:Zutfen-LLC/zadc/pull/1",
    source=zadc.ObservationSource(source_type="github", source_id="github:Zutfen-LLC/zadc"),
    observed_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc),
    statement="smoke observed", epistemic_status="AGENT_REPORTED", evidence_refs=[],
    freshness_seconds=None, expires_at=None,
)

for artifact in [packet, completion_report, certification_manifest, evidence_artifact, observation]:
    sealed = zadc.seal_artifact(artifact)
    assert type(sealed) is type(artifact)
    assert sealed.provenance.content_digest is not None
    data = json.loads(zadc.canonical_json_text(sealed))
    reloaded = type(sealed).model_validate(data)
    zadc.verify_content_digest(reloaded)

print("A2A_SMOKE_OK")
"""


@pytest.fixture
def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestA2APackageSmokeCleanVenv:
    """Clean-venv wheel smoke covering all five A2A artifact classes."""

    def test_wheel_all_five_artifacts_construct_seal_verify(self, repo_root: str) -> None:
        dist_dir = os.path.join(repo_root, "dist")
        wheels = glob.glob(os.path.join(dist_dir, "*.whl"))
        if not wheels:
            pytest.skip("dist/ not built yet — run 'make build' first")

        wheel = wheels[0]
        python = sys.executable

        with tempfile.TemporaryDirectory(prefix="zadc-a2a-smoke-") as tmpdir:
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

            script_path = os.path.join(tmpdir, "a2a_smoke.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(_SMOKE_SCRIPT)

            result = subprocess.run([venv_python, script_path], capture_output=True, text=True)
            assert result.returncode == 0, (
                f"A2A smoke test failed: {result.stderr}\nstdout: {result.stdout}"
            )
            assert "A2A_SMOKE_OK" in result.stdout
