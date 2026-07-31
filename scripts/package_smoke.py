#!/usr/bin/env python3
"""Package smoke test: install the wheel into a clean venv and verify import + CLI."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def find_wheel(dist_dir: Path) -> Path:
    wheels = glob.glob(str(dist_dir / "*.whl"))
    if not wheels:
        print("FAIL: No wheel found in dist/")
        sys.exit(1)
    return Path(wheels[0])


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = repo_root / "dist"
    python = sys.executable

    if not dist_dir.exists():
        print("FAIL: dist/ directory not found. Run 'make build' first.")
        return 1

    wheel = find_wheel(dist_dir)
    print(f"Testing wheel: {wheel.name}")

    with tempfile.TemporaryDirectory(prefix="zadc-smoke-") as tmpdir:
        venv_dir = os.path.join(tmpdir, "venv")
        venv_python = os.path.join(venv_dir, "bin", "python")

        # Create clean venv (no system packages)
        print("Creating clean virtual environment...")
        result = subprocess.run(
            [python, "-m", "venv", venv_dir],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"FAIL: Could not create venv: {result.stderr}")
            return 1

        # Install the wheel (with runtime dependencies)
        print(f"Installing {wheel.name}...")
        result = subprocess.run(
            [venv_python, "-m", "pip", "install", str(wheel)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"FAIL: pip install failed: {result.stderr}")
            return 1

        # Test import + version
        print("Testing import...")
        result = subprocess.run(
            [venv_python, "-c", "import zadc; print(zadc.get_version())"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"FAIL: import zadc failed: {result.stderr}")
            return 1
        print(f"  import zadc -> {result.stdout.strip()}")

        # Test full envelope workflow
        print("Testing envelope workflow...")
        workflow_code = (
            "import zadc\n"
            "from datetime import datetime, timezone\n"
            "import json\n"
            "env = zadc.ArtifactEnvelope(\n"
            "    schema=zadc.SCHEMA_ID,\n"
            "    contract_version=zadc.CONTRACT_VERSION,\n"
            '    artifact_type="packet",\n'
            '    artifact_id="urn:uuid:00000000-0000-0000-0000-000000000070",\n'
            "    created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc),\n"
            "    producer=zadc.ProducerIdentity(\n"
            '        actor_type="human", actor_id="zutfen:human:smoke"),\n'
            '    project_id="zutfen:project:zadc",\n'
            '    slice_id="SMOKE-001", slice_instance_id="SMOKE-001A",\n'
            "    policy=zadc.PolicyReference(\n"
            '        policy_id="zutfen:zadc-policy:standard@0.1.0",\n'
            '        policy_source_sha="a" * 40,\n'
            '        policy_digest="sha256:" + "b" * 64,\n'
            "    ),\n"
            "    provenance=zadc.Provenance(parent_artifact_ids=()),\n"
            ")\n"
            "sealed = zadc.seal_artifact(env)\n"
            "assert sealed.provenance.content_digest is not None\n"
            "data = json.loads(zadc.canonical_json_text(sealed))\n"
            "reloaded = zadc.ArtifactEnvelope.model_validate(data)\n"
            "zadc.verify_content_digest(reloaded)\n"
            "print('WORKFLOW_OK')\n"
        )
        result = subprocess.run(
            [venv_python, "-c", workflow_code],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"FAIL: envelope workflow failed: {result.stderr}")
            return 1
        if "WORKFLOW_OK" not in result.stdout:
            print(f"FAIL: envelope workflow did not print WORKFLOW_OK: {result.stdout}")
            return 1
        print("  envelope workflow -> WORKFLOW_OK")

        # Test --version
        print("Testing zadc --version...")
        cli = os.path.join(venv_dir, "bin", "zadc")
        result = subprocess.run(
            [cli, "--version"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"FAIL: zadc --version failed: {result.stderr}")
            return 1
        print("  zadc --version -> exit 0")

        # Test --help
        print("Testing zadc --help...")
        result = subprocess.run(
            [cli, "--help"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"FAIL: zadc --help failed: {result.stderr}")
            return 1
        print("  zadc --help -> exit 0")

        # Test python -m zadc --version
        print("Testing python -m zadc --version...")
        result = subprocess.run(
            [venv_python, "-m", "zadc", "--version"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"FAIL: python -m zadc --version failed: {result.stderr}")
            return 1
        print("  python -m zadc --version -> exit 0")

    print("\nOK: All package smoke tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
