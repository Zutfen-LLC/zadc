"""A3A: clean-venv wheel smoke test covering the rendering foundation.

Constructs and seals representative concrete artifacts (covering the
ReviewReport/DecisionRecord/WorkflowBundle caveat paths), then renders each
through both default renderers from a clean virtual environment with only the
built wheel installed — proving the rendering layer imports and works without
the source tree. Mirrors ``tests/test_a2b2_package_smoke.py``.
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
    "RenderConsumer", "RendererReference", "RenderedView", "RendererProtocol",
    "RendererRegistry", "HumanMarkdownRenderer", "CiJsonRenderer",
    "DEFAULT_RENDERER_REGISTRY", "render_artifact", "RendererNotFoundError",
]
for name in required_names:
    assert hasattr(zadc, name), f"zadc is missing public name: {name}"

assert set(zadc.DEFAULT_RENDERER_REGISTRY.consumers) == {"human", "ci"}

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
    policy_source_sha=SHA_A, policy_digest=DIGEST_B,
)


def envelope_kwargs(artifact_type, artifact_id, producer=human_producer):
    return dict(
        schema=zadc.SCHEMA_ID, contract_version=zadc.CONTRACT_VERSION,
        artifact_type=artifact_type, artifact_id=artifact_id,
        created_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
        producer=producer, project_id="zutfen:project:zadc",
        slice_id="SMOKE-A3A", slice_instance_id="SMOKE-A3A1",
        policy=policy, provenance=zadc.Provenance(parent_artifact_ids=()),
    )


def sealed_ref(artifact):
    sealed = zadc.seal_artifact(artifact)
    return zadc.ArtifactReference(
        artifact_id=sealed.artifact_id, content_digest=sealed.provenance.content_digest
    )


packet = zadc.Packet(
    **envelope_kwargs("packet", "urn:uuid:00000000-0000-0000-0000-000000000501"),
    authorization=zadc.PacketAuthorization(
        authorized_by="zutfen:human:smoke",
        authorized_at=datetime(2026, 8, 1, 11, 0, 0, tzinfo=timezone.utc),
    ),
    repository=zadc.RepositoryTarget(
        repository_id="github:Zutfen-LLC/zadc", provider="github",
        owner="Zutfen-LLC", name="zadc",
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

review_report = zadc.ReviewReport(
    **envelope_kwargs("review_report", "urn:uuid:00000000-0000-0000-0000-000000000502"),
    packet_id=packet.artifact_id,
    review_id="urn:uuid:00000000-0000-0000-0000-000000000502",
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
    **envelope_kwargs("decision_record", "urn:uuid:00000000-0000-0000-0000-000000000503"),
    decision_id="urn:uuid:00000000-0000-0000-0000-000000000503",
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

bundle_id = "urn:uuid:00000000-0000-0000-0000-000000000504"
derived_state = zadc.DerivedStateSnapshot(
    state="awaiting_review",
    computed_at=datetime(2026, 8, 1, 11, 30, 0, tzinfo=timezone.utc),
    validator_actor_id="zutfen:validator:smoke",
    validator_run_id="urn:uuid:00000000-0000-0000-0000-000000000901",
    policy=policy,
    input_artifact_refs=[sealed_ref(packet)], blockers=[], stale_artifact_refs=[],
    next_admissible_actions=["submit_review"],
)
workflow_bundle = zadc.WorkflowBundle(
    **envelope_kwargs("workflow_bundle", bundle_id, producer=validator_producer),
    bundle_id=bundle_id, packet_ref=sealed_ref(packet),
    agent_run_refs=[
        zadc.AgentRunReference(
            run_id="urn:uuid:00000000-0000-0000-0000-000000000902",
            executor_actor_id="zutfen:agent:hermes",
        )
    ],
    completion_report_refs=[], certification_manifest_refs=[],
    evidence_artifact_refs=[], review_report_refs=[sealed_ref(review_report)],
    decision_record_refs=[sealed_ref(decision_record)], observation_refs=[],
    supersedes_bundle_ref=None, derived_state=derived_state,
)

render_at = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
for artifact in [packet, review_report, decision_record, workflow_bundle]:
    sealed = zadc.seal_artifact(artifact)
    before = zadc.canonical_json_text(sealed)

    human = zadc.render_artifact(sealed, rendered_at=render_at, consumer="human")
    assert human.non_authoritative is True
    assert human.source_ref.artifact_id == sealed.artifact_id
    assert human.source_ref.content_digest == sealed.provenance.content_digest
    assert human.media_type == "text/markdown"
    assert human.content.startswith("# NON-AUTHORITATIVE RENDERED VIEW")

    ci = zadc.render_artifact(sealed, rendered_at=render_at, consumer="ci")
    assert ci.source_ref == human.source_ref
    assert ci.media_type == "application/json"
    payload = json.loads(ci.content)
    assert payload["non_authoritative"] is True
    assert payload["source_artifact"]["artifact_id"] == sealed.artifact_id

    # Source is byte-identical after rendering.
    assert before == zadc.canonical_json_text(sealed)
    zadc.verify_content_digest(sealed)

# Reserved consumers have no renderer and fail explicitly.
try:
    zadc.DEFAULT_RENDERER_REGISTRY.get("hermes")
    raise SystemExit("expected RendererNotFoundError for hermes")
except zadc.RendererNotFoundError:
    pass

print("A3A_SMOKE_OK")
"""


@pytest.fixture
def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestA3APackageSmokeCleanVenv:
    """Clean-venv wheel smoke covering the rendering foundation."""

    def test_wheel_rendering_imports_and_renders(self, repo_root: str) -> None:
        dist_dir = os.path.join(repo_root, "dist")
        wheels = glob.glob(os.path.join(dist_dir, "*.whl"))
        if not wheels:
            pytest.skip("dist/ not built yet — run 'make build' first")

        wheel = wheels[0]
        python = sys.executable

        with tempfile.TemporaryDirectory(prefix="zadc-a3a-smoke-") as tmpdir:
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

            script_path = os.path.join(tmpdir, "a3a_smoke.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(_SMOKE_SCRIPT)

            result = subprocess.run([venv_python, script_path], capture_output=True, text=True)
            assert result.returncode == 0, (
                f"A3A smoke test failed: {result.stderr}\nstdout: {result.stdout}"
            )
            assert "A3A_SMOKE_OK" in result.stdout
