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

        # Test import
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
