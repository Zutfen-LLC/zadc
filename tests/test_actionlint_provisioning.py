"""Behavioral proof tests for actionlint provisioning (ZADC-000-FIX2).

These tests execute the real provisioning code paths and assert observable
behavior — they do not search source text for strings. Each test
corresponds to a behavioral proof (BT-01 through BT-07) required by the
ZADC-000-FIX2 fix packet.

Test seams use environment variables (ACTIONLINT_TEST_*) that are gated by
ACTIONLINT_TEST_HARNESS=1 and rejected in CI mode (CI=true) unless the
harness explicitly enables them. These seams never weaken checksum or
version verification — they only control what gets downloaded and what
digest is expected.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_actionlint.sh"
RUN_LINT_SCRIPT = REPO_ROOT / "scripts" / "run_workflow_lint.sh"

# Official v1.7.12 release checksums (from actionlint_1.7.12_checksums.txt)
# Maps (os_raw, arch_raw) -> (expected_asset_filename, expected_sha256)
PLATFORM_MATRIX = [
    (
        "Linux",
        "x86_64",
        "actionlint_1.7.12_linux_amd64.tar.gz",
        "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
    ),
    (
        "Linux",
        "aarch64",
        "actionlint_1.7.12_linux_arm64.tar.gz",
        "325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6",
    ),
    (
        "Darwin",
        "x86_64",
        "actionlint_1.7.12_darwin_amd64.tar.gz",
        "5b44c3bc2255115c9b69e30efc0fecdf498fdb63c5d58e17084fd5f16324c644",
    ),
    (
        "Darwin",
        "arm64",
        "actionlint_1.7.12_darwin_arm64.tar.gz",
        "aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f",
    ),
]


def _run_script(
    args: list[str],
    env: dict[str, str] | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Run a shell script and capture output."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        ["bash", *args],
        capture_output=True,
        text=True,
        env=full_env,
        cwd=str(REPO_ROOT),
        timeout=timeout,
    )


# ===========================================================================
# BT-01: Supported platform selection
# ===========================================================================


class TestBT01SupportedPlatformSelection:
    """Execute the provisioning selection logic for all four supported host
    tuples and assert the exact expected asset and digest are selected."""

    @pytest.mark.parametrize(
        "os_name,arch,expected_asset,expected_sha",
        PLATFORM_MATRIX,
        ids=["linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64"],
    )
    def test_selects_exact_asset_for_each_tuple(
        self, os_name: str, arch: str, expected_asset: str, expected_sha: str
    ) -> None:
        """Each supported tuple selects the exact committed asset and digest."""
        result = _run_script(
            [str(INSTALL_SCRIPT), "--print-selection"],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": os_name,
                "ACTIONLINT_TEST_ARCH": arch,
            },
        )
        assert result.returncode == 0, f"Selection failed for {os_name}/{arch}: {result.stderr}"
        parts = result.stdout.strip().split()
        assert len(parts) == 2, f"Expected 'asset sha256', got: {result.stdout!r}"
        asset, sha = parts
        assert asset == expected_asset, (
            f"Wrong asset for {os_name}/{arch}: expected {expected_asset}, got {asset}"
        )
        assert sha == expected_sha, (
            f"Wrong SHA-256 for {os_name}/{arch}: expected {expected_sha}, got {sha}"
        )

    @pytest.mark.parametrize(
        "alias,canonical",
        [
            ("x86_64", "amd64"),
            ("amd64", "amd64"),
            ("aarch64", "arm64"),
            ("arm64", "arm64"),
        ],
    )
    def test_arch_aliases_normalize_correctly(self, alias: str, canonical: str) -> None:
        """Common uname aliases (x86_64/amd64, aarch64/arm64) normalize to the
        same canonical identifier and produce the same selection."""
        os_name = "Linux"
        result_alias = _run_script(
            [str(INSTALL_SCRIPT), "--print-selection"],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": os_name,
                "ACTIONLINT_TEST_ARCH": alias,
            },
        )
        result_canonical = _run_script(
            [str(INSTALL_SCRIPT), "--print-selection"],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": os_name,
                "ACTIONLINT_TEST_ARCH": canonical,
            },
        )
        # Only amd64 and arm64 have aliases in the supported set
        if canonical in ("amd64", "arm64"):
            assert result_alias.returncode == 0
            assert result_canonical.returncode == 0
            assert result_alias.stdout.strip() == result_canonical.stdout.strip(), (
                f"Alias {alias} should produce same selection as {canonical}"
            )


# ===========================================================================
# BT-02: Unsupported platform fails closed
# ===========================================================================


class TestBT02UnsupportedPlatformFailsClosed:
    """Execute the real provisioning path with a simulated unsupported uname
    tuple and assert nonzero exit plus an actionable error."""

    def test_unsupported_os_fails_closed(self) -> None:
        result = _run_script(
            [str(INSTALL_SCRIPT), "--print-selection"],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "FreeBSD",
                "ACTIONLINT_TEST_ARCH": "x86_64",
            },
        )
        assert result.returncode != 0, "Unsupported OS must fail closed"
        assert "Unsupported" in result.stderr or "FAIL" in result.stderr

    def test_unsupported_arch_fails_closed(self) -> None:
        result = _run_script(
            [str(INSTALL_SCRIPT), "--print-selection"],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "riscv64",
            },
        )
        assert result.returncode != 0, "Unsupported arch must fail closed"
        assert "Unsupported" in result.stderr or "FAIL" in result.stderr

    def test_unsupported_os_error_is_actionable(self) -> None:
        """Error message must list supported platforms for the user."""
        result = _run_script(
            [str(INSTALL_SCRIPT), "--print-selection"],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Windows",
                "ACTIONLINT_TEST_ARCH": "x86_64",
            },
        )
        assert result.returncode != 0
        stderr_lower = result.stderr.lower()
        assert "supported" in stderr_lower or "linux" in stderr_lower


# ===========================================================================
# BT-03: Checksum mismatch fails closed
# ===========================================================================


class TestBT03ChecksumMismatchFailsClosed:
    """Execute the real installer against a controlled corrupted fixture and
    assert it exits nonzero before extraction or execution."""

    def test_corrupted_download_rejected(self, tmp_path: Path) -> None:
        """A valid-looking tarball with wrong content must fail checksum."""
        # Create a valid tar.gz file with wrong content
        fake_tarball = tmp_path / "actionlint_1.7.12_linux_amd64.tar.gz"
        dummy_bin = tmp_path / "actionlint"
        dummy_bin.write_text("this is not actionlint")
        with tarfile.open(fake_tarball, "w:gz") as tar:
            tar.add(dummy_bin, arcname="actionlint")

        # Expected sha = the real committed one; actual will differ -> mismatch
        result = _run_script(
            [str(INSTALL_SCRIPT), str(tmp_path / "installdir")],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": f"file://{fake_tarball}",
                # Keep the real expected SHA so the corrupted fixture mismatches
            },
        )
        assert result.returncode != 0, "Checksum mismatch must fail closed"
        assert "SHA-256 mismatch" in result.stderr or "mismatch" in result.stderr.lower()
        # Must fail BEFORE extraction or execution — no actionlint binary installed
        assert not (tmp_path / "installdir" / "actionlint").exists(), (
            "Corrupted download must not be extracted"
        )


# ===========================================================================
# BT-04: Download failure fails closed
# ===========================================================================


class TestBT04DownloadFailureFailsClosed:
    """Execute the real installer with a controlled failed downloader and
    assert nonzero exit."""

    def test_nonexistent_url_fails_closed(self, tmp_path: Path) -> None:
        """A URL that returns 404 must produce a nonzero exit."""
        result = _run_script(
            [str(INSTALL_SCRIPT), str(tmp_path / "installdir")],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": (
                    "https://github.com/rhysd/actionlint/releases/download/"
                    "v1.7.12/DOES_NOT_EXIST.tar.gz"
                ),
            },
        )
        assert result.returncode != 0, "Download failure must fail closed"
        assert "download" in result.stderr.lower() or "fail" in result.stderr.lower()

    def test_file_url_to_nonexistent_path_fails(self, tmp_path: Path) -> None:
        """A file:// URL pointing to a nonexistent path must fail."""
        result = _run_script(
            [str(INSTALL_SCRIPT), str(tmp_path / "installdir")],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": f"file://{tmp_path}/does_not_exist.tar.gz",
            },
        )
        assert result.returncode != 0


# ===========================================================================
# BT-05: Version mismatch fails closed
# ===========================================================================


class TestBT05VersionMismatchFailsClosed:
    """Provide a controlled binary reporting the wrong actionlint version and
    assert it is rejected."""

    def test_wrong_version_rejected(self, tmp_path: Path) -> None:
        """A binary that passes checksum (using a matching override SHA) but
        reports the wrong version must be rejected."""
        # Build a fake tarball containing a shell script that reports v9.9.9
        fake_bin_content = '#!/usr/bin/env bash\necho "1.99.99"\n'
        fake_tarball = tmp_path / "actionlint_1.7.12_linux_amd64.tar.gz"
        staging = tmp_path / "staging"
        staging.mkdir()
        fake_bin = staging / "actionlint"
        fake_bin.write_text(fake_bin_content)
        fake_bin.chmod(0o755)
        with tarfile.open(fake_tarball, "w:gz") as tar:
            tar.add(fake_bin, arcname="actionlint")

        # Compute the actual SHA of our fake tarball so checksum passes
        actual_sha = hashlib.sha256(fake_tarball.read_bytes()).hexdigest()

        result = _run_script(
            [str(INSTALL_SCRIPT), str(tmp_path / "installdir")],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": f"file://{fake_tarball}",
                "ACTIONLINT_TEST_SHA256": actual_sha,  # checksum will pass
            },
        )
        assert result.returncode != 0, "Version mismatch must fail closed even when checksum passes"
        assert "version mismatch" in result.stderr.lower() or "version" in result.stderr.lower()


# ===========================================================================
# BT-06: Missing uv fails closed
# ===========================================================================


class TestBT06MissingUvFailsClosed:
    """Execute scripts/run_workflow_lint.sh in a controlled PATH without uv
    and assert nonzero exit."""

    def test_run_workflow_lint_fails_without_uv(self) -> None:
        """run_workflow_lint.sh must exit nonzero when uv is not on PATH."""
        # Build a minimal PATH with only essential utilities (bash, coreutils)
        # but NO uv. Use /usr/bin and /bin which have bash, curl, etc.
        stripped_path = "/usr/bin:/bin"
        # Verify uv is NOT on this stripped path
        uv_check = subprocess.run(
            ["bash", "-c", f'PATH="{stripped_path}" command -v uv'],
            capture_output=True,
            text=True,
        )
        if uv_check.stdout.strip():
            pytest.skip("uv found on stripped path; cannot test missing-uv path")

        result = subprocess.run(
            ["bash", str(RUN_LINT_SCRIPT)],
            capture_output=True,
            text=True,
            env={
                "PATH": stripped_path,
                "HOME": os.environ.get("HOME", "/tmp"),
                "CI": "",  # not in CI
            },
            cwd=str(REPO_ROOT),
            timeout=30,
        )
        assert result.returncode != 0, "Missing uv must fail closed"
        assert "uv" in result.stderr.lower()


# ===========================================================================
# BT-07: Happy path remains green
# ===========================================================================
# The BT-07 happy-path proof is the real ``make workflow-lint`` command,
# executed as a standalone local verification (recorded in the completion
# report) and as the CI ``workflow-lint`` job on the exact PR head SHA.
# It is deliberately NOT a pytest test because calling ``make workflow-lint``
# from inside pytest mutates the shared ``.venv`` (uv recreates it for the
# default Python), which breaks subsequent tests in the CI matrix.
