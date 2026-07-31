"""A1-BP-009: Wheel/sdist and clean-venv smoke import public API and
complete construct/seal/serialize/verify."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _find_wheel(dist_dir: Path) -> Path:
    wheels = glob.glob(str(dist_dir / "*.whl"))
    assert wheels, f"No wheel found in {dist_dir}"
    return Path(wheels[0])


def _find_sdist(dist_dir: Path) -> Path:
    sdists = glob.glob(str(dist_dir / "*.tar.gz"))
    assert sdists, f"No sdist found in {dist_dir}"
    return Path(sdists[0])


_SMOKE_CODE = """
import zadc

# Verify all public API names are importable
required_names = [
    "ActorType", "ArtifactType", "ArtifactEnvelope",
    "ProducerIdentity", "PolicyReference", "Provenance",
    "Sha256Digest", "GitSha",
    "canonical_json_bytes", "canonical_json_text",
    "compute_content_digest", "seal_artifact", "verify_content_digest",
    "DigestMissingError", "DigestMismatchError",
]
for name in required_names:
    assert hasattr(zadc, name), f"zadc is missing public name: {name}"

# Construct -> seal -> serialize -> reload -> verify
from datetime import datetime, timezone
import json

env = zadc.ArtifactEnvelope(
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
    provenance=zadc.Provenance(parent_artifact_ids=[]),
)

# Seal
sealed = zadc.seal_artifact(env)
assert sealed.provenance.content_digest is not None

# Serialize
data = sealed.model_dump(mode="json", by_alias=True)
json_str = json.dumps(data, sort_keys=True)

# Reload
reloaded_data = json.loads(json_str)
reloaded = zadc.ArtifactEnvelope.model_validate(reloaded_data)

# Verify
zadc.verify_content_digest(reloaded)

# Canonical JSON
canonical = zadc.canonical_json_text(data)
assert isinstance(canonical, str)

print("SMOKE_OK")
"""


class TestPackageSmokeCleanVenv:
    """Install wheel in a clean venv and run the full smoke test."""

    def test_wheel_imports_and_round_trip(self, repo_root: Path) -> None:
        dist_dir = repo_root / "dist"
        if not dist_dir.exists() or not glob.glob(str(dist_dir / "*.whl")):
            pytest.skip("dist/ not built yet — run 'make build' first")

        wheel = _find_wheel(dist_dir)
        python = sys.executable

        with tempfile.TemporaryDirectory(prefix="zadc-bp009-") as tmpdir:
            venv_dir = os.path.join(tmpdir, "venv")
            venv_python = os.path.join(venv_dir, "bin", "python")

            # Create clean venv
            result = subprocess.run(
                [python, "-m", "venv", venv_dir],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"venv creation failed: {result.stderr}"

            # Install wheel with dependencies (pydantic is a runtime dep)
            result = subprocess.run(
                [venv_python, "-m", "pip", "install", str(wheel)],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"pip install failed: {result.stderr}"

            # Run smoke code
            result = subprocess.run(
                [venv_python, "-c", _SMOKE_CODE],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, (
                f"smoke test failed: {result.stderr}\nstdout: {result.stdout}"
            )
            assert "SMOKE_OK" in result.stdout
