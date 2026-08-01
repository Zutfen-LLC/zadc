"""A2B1: clean-venv wheel smoke test covering ReviewReport and DecisionRecord.

Constructs, seals, canonicalizes, reloads, and verifies a ReviewReport and a
DecisionRecord from a clean virtual environment with only the built wheel
installed — mirroring ``tests/test_a2a_package_smoke.py``.
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
    "ReviewReport", "ReviewerIdentity", "ReviewIndependence", "ReviewSubject",
    "ReviewedFile", "ReviewInputs", "FileFindingLocation", "ArtifactFindingLocation",
    "GeneralFindingLocation", "FindingLocation", "Finding",
    "DecisionRecord", "HumanDecisionIdentity", "DecisionSubject", "AcceptedRisk",
    "FindingStatus", "ReviewerRecommendation", "DecisionType", "FindingLocationType",
]
for name in required_names:
    assert hasattr(zadc, name), f"zadc is missing public name: {name}"

SHA_A = "a" * 40
SHA_B = "b" * 40
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64

reviewer_producer = zadc.ProducerIdentity(actor_type="human", actor_id="zutfen:human:reviewer")
human_producer = zadc.ProducerIdentity(actor_type="human", actor_id="zutfen:human:decider")
policy = zadc.PolicyReference(
    policy_id="zutfen:zadc-policy:standard@0.1.0",
    policy_source_sha=SHA_A,
    policy_digest=DIGEST_B,
)


def envelope_kwargs(artifact_type, artifact_id, producer):
    return dict(
        schema=zadc.SCHEMA_ID,
        contract_version=zadc.CONTRACT_VERSION,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc),
        producer=producer,
        project_id="zutfen:project:zadc",
        slice_id="SMOKE-001A2B1",
        slice_instance_id="SMOKE-001A2B11",
        policy=policy,
        provenance=zadc.Provenance(parent_artifact_ids=()),
    )


review_report = zadc.ReviewReport(
    **envelope_kwargs(
        "review_report", "urn:uuid:00000000-0000-0000-0000-000000000201", reviewer_producer
    ),
    packet_id="urn:uuid:00000000-0000-0000-0000-000000000001",
    review_id="urn:uuid:00000000-0000-0000-0000-000000000201",
    reviewer=zadc.ReviewerIdentity(actor_type="human", actor_id="zutfen:human:reviewer"),
    independence=zadc.ReviewIndependence(
        executor_actor_id="zutfen:agent:hermes", satisfied=True
    ),
    subject=zadc.ReviewSubject(
        repository_id="github:Zutfen-LLC/zadc",
        review_subject_sha=SHA_B,
        packet_digest=DIGEST_C,
        certification_manifest_ids=[],
    ),
    inputs_reviewed=zadc.ReviewInputs(diffs=[], files=[], evidence_artifacts=[]),
    findings=[
        zadc.Finding(
            finding_id="F-1",
            severity="minor",
            status="open",
            location=zadc.GeneralFindingLocation(location_type="general", description="note"),
            statement="smoke finding",
            rationale="smoke rationale",
            resolution_refs=[],
        )
    ],
    limitations=[],
    reviewer_recommendation="green_for_review",
)

decision_record = zadc.DecisionRecord(
    **envelope_kwargs(
        "decision_record", "urn:uuid:00000000-0000-0000-0000-000000000202", human_producer
    ),
    decision_id="urn:uuid:00000000-0000-0000-0000-000000000202",
    decided_by=zadc.HumanDecisionIdentity(actor_type="human", actor_id="zutfen:human:decider"),
    decided_at=datetime(2026, 7, 31, 13, 0, 0, tzinfo=timezone.utc),
    subject=zadc.DecisionSubject(
        repository_id="github:Zutfen-LLC/zadc",
        pull_request=42,
        decision_subject_sha=SHA_B,
        current_pr_head_sha_observed=SHA_B,
        review_report_ids=[review_report.artifact_id],
        certification_manifest_ids=[],
    ),
    decision="approve_for_merge",
    accepted_risks=[],
    supersedes_decision_ref=None,
    conditions=[],
    rationale="smoke approval",
)

for artifact in [review_report, decision_record]:
    sealed = zadc.seal_artifact(artifact)
    assert type(sealed) is type(artifact)
    assert sealed.provenance.content_digest is not None
    data = json.loads(zadc.canonical_json_text(sealed))
    reloaded = type(sealed).model_validate(data)
    zadc.verify_content_digest(reloaded)

print("A2B1_SMOKE_OK")
"""


@pytest.fixture
def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestA2B1PackageSmokeCleanVenv:
    """Clean-venv wheel smoke covering ReviewReport and DecisionRecord."""

    def test_wheel_review_and_decision_artifacts_construct_seal_verify(
        self, repo_root: str
    ) -> None:
        dist_dir = os.path.join(repo_root, "dist")
        wheels = glob.glob(os.path.join(dist_dir, "*.whl"))
        if not wheels:
            pytest.skip("dist/ not built yet — run 'make build' first")

        wheel = wheels[0]
        python = sys.executable

        with tempfile.TemporaryDirectory(prefix="zadc-a2b1-smoke-") as tmpdir:
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

            script_path = os.path.join(tmpdir, "a2b1_smoke.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(_SMOKE_SCRIPT)

            result = subprocess.run([venv_python, script_path], capture_output=True, text=True)
            assert result.returncode == 0, (
                f"A2B1 smoke test failed: {result.stderr}\nstdout: {result.stdout}"
            )
            assert "A2B1_SMOKE_OK" in result.stdout
