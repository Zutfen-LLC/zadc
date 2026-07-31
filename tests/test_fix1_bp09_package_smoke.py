"""FIX1-BP-09: Package/API documentation remains usable.

Clean-venv wheel/sdist smoke constructs, seals, directly canonicalizes,
reloads, and verifies an envelope.
"""

import glob
import os
import subprocess
import sys
import tempfile

import pytest

_SMOKE_CODE = """
import zadc

required_names = [
    "ActorType", "ArtifactType", "ArtifactEnvelope",
    "ProducerIdentity", "PolicyReference", "Provenance",
    "GlobalId", "SliceId", "Sha256Digest", "GitSha",
    "canonical_json_bytes", "canonical_json_text",
    "compute_content_digest", "seal_artifact", "verify_content_digest",
    "DigestMissingError", "DigestMismatchError",
]
for name in required_names:
    assert hasattr(zadc, name), f"zadc is missing public name: {name}"

from datetime import datetime, timezone
import json

env = zadc.ArtifactEnvelope(
    schema=zadc.SCHEMA_ID,
    contract_version=zadc.CONTRACT_VERSION,
    artifact_type="packet",
    artifact_id="urn:uuid:00000000-0000-0000-0000-000000000050",
    created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc),
    producer=zadc.ProducerIdentity(
        actor_type="human", actor_id="zutfen:human:smoke"
    ),
    project_id="zutfen:project:zadc",
    slice_id="SMOKE-001",
    slice_instance_id="SMOKE-001A",
    policy=zadc.PolicyReference(
        policy_id="zutfen:zadc-policy:standard@0.1.0",
        policy_source_sha="a" * 40,
        policy_digest="sha256:" + "b" * 64,
    ),
    provenance=zadc.Provenance(parent_artifact_ids=()),
)

# Direct model canonicalization (FIX1-C)
canonical = zadc.canonical_json_text(env)
assert isinstance(canonical, str)

# Seal (FIX1-B)
sealed = zadc.seal_artifact(env)
assert sealed.provenance.content_digest is not None

# Serialize and reload
data = json.loads(zadc.canonical_json_text(sealed))
reloaded = zadc.ArtifactEnvelope.model_validate(data)

# Verify (FIX1-A)
zadc.verify_content_digest(reloaded)

print("SMOKE_OK")
"""


@pytest.fixture
def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestPackageSmokeCleanVenv:
    """Clean-venv wheel/sdist smoke test."""

    def test_wheel_construct_seal_canonicalize_reload_verify(self, repo_root: str) -> None:
        dist_dir = os.path.join(repo_root, "dist")
        wheels = glob.glob(os.path.join(dist_dir, "*.whl"))
        if not wheels:
            pytest.skip("dist/ not built yet — run 'make build' first")

        wheel = wheels[0]
        python = sys.executable

        with tempfile.TemporaryDirectory(prefix="zadc-fix1-bp09-") as tmpdir:
            venv_dir = os.path.join(tmpdir, "venv")
            venv_python = os.path.join(venv_dir, "bin", "python")

            result = subprocess.run(
                [python, "-m", "venv", venv_dir],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

            result = subprocess.run(
                [venv_python, "-m", "pip", "install", wheel],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"pip install failed: {result.stderr}"

            result = subprocess.run(
                [venv_python, "-c", _SMOKE_CODE],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, (
                f"smoke test failed: {result.stderr}\nstdout: {result.stdout}"
            )
            assert "SMOKE_OK" in result.stdout
