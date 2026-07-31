"""Behavioral proof tests for actionlint provisioning (ZADC-000-FIX3).

These tests execute the real provisioning code paths and assert observable
behavior. Each test corresponds to a behavioral proof (BT3-01 through BT3-08)
required by the ZADC-000-FIX3 fix packet. BT3-09 is the standalone
make workflow-lint proof, recorded separately.

All negative-path tests are offline and deterministic — no external network,
no pytest.skip.
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_actionlint.sh"
RUN_LINT_SCRIPT = REPO_ROOT / "scripts" / "run_workflow_lint.sh"

# Official v1.7.12 release checksums (from actionlint_1.7.12_checksums.txt)
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

OVERRIDE_VARS = [
    "ACTIONLINT_TEST_OS",
    "ACTIONLINT_TEST_ARCH",
    "ACTIONLINT_TEST_URL",
    "ACTIONLINT_TEST_SHA256",
    "ACTIONLINT_TEST_CURL",
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


def _make_valid_tarball(tmp_path: Path, name: str, content: str) -> Path:
    """Create a valid tar.gz with an 'actionlint' entry containing content."""
    tarball = tmp_path / name
    staging = tmp_path / "staging_make"
    staging.mkdir(exist_ok=True, parents=True)
    fake_bin = staging / "actionlint"
    fake_bin.write_text(content)
    fake_bin.chmod(0o755)
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(fake_bin, arcname="actionlint")
    return tarball


def _make_failing_curl_shim(tmp_path: Path) -> Path:
    """Create a curl shim that always exits nonzero (for offline download-failure tests)."""
    shim = tmp_path / "curl_fail"
    shim.write_text("#!/usr/bin/env bash\nexit 1\n")
    shim.chmod(0o755)
    return shim


# ===========================================================================
# BT3-01: Override without harness is rejected
# ===========================================================================


class TestBT301OverrideWithoutHarnessRejected:
    """For each ACTIONLINT_TEST_* override class, execute the real installer
    without ACTIONLINT_TEST_HARNESS=1 and prove immediate nonzero rejection
    before download or installation."""

    @pytest.mark.parametrize("override_var", OVERRIDE_VARS, ids=OVERRIDE_VARS)
    def test_override_rejected_without_harness(self, override_var: str, tmp_path: Path) -> None:
        """Each override variable must be rejected without the harness."""
        env = {
            override_var: "test_value",
            # Explicitly ensure harness is NOT set
            "ACTIONLINT_TEST_HARNESS": "",
        }
        result = _run_script(
            [str(INSTALL_SCRIPT), str(tmp_path / "installdir")],
            env=env,
        )
        assert result.returncode != 0, (
            f"{override_var} must be rejected without ACTIONLINT_TEST_HARNESS=1"
        )
        assert override_var in result.stderr
        assert "ACTIONLINT_TEST_HARNESS" in result.stderr

    def test_override_rejected_completely_unset_harness(self, tmp_path: Path) -> None:
        """When harness is completely unset, overrides must be rejected."""
        env = os.environ.copy()
        # Remove harness entirely
        env.pop("ACTIONLINT_TEST_HARNESS", None)
        env["ACTIONLINT_TEST_OS"] = "Linux"
        result = _run_script(
            [str(INSTALL_SCRIPT), "--print-selection"],
            env=env,
        )
        assert result.returncode != 0
        assert "ACTIONLINT_TEST_HARNESS" in result.stderr


# ===========================================================================
# BT3-02: Invalid harness values are rejected
# ===========================================================================


class TestBT302InvalidHarnessValuesRejected:
    """Prove unset, empty, 0, true, yes, and other non-1 values do not
    authorize overrides."""

    @pytest.mark.parametrize(
        "harness_value",
        ["", "0", "true", "yes", "2", "on", "enabled", "yes "],
        ids=["empty", "zero", "true", "yes", "two", "on", "enabled", "yes-space"],
    )
    def test_invalid_harness_rejects_override(self, harness_value: str, tmp_path: Path) -> None:
        """Non-1 harness values must not authorize overrides."""
        env = {
            "ACTIONLINT_TEST_HARNESS": harness_value,
            "ACTIONLINT_TEST_OS": "Linux",
        }
        result = _run_script(
            [str(INSTALL_SCRIPT), "--print-selection"],
            env=env,
        )
        assert result.returncode != 0, (
            f"Harness value '{harness_value}' must not authorize overrides"
        )

    def test_harness_1_with_override_works(self, tmp_path: Path) -> None:
        """Exact string '1' is the only value that authorizes overrides."""
        env = {
            "ACTIONLINT_TEST_HARNESS": "1",
            "ACTIONLINT_TEST_OS": "Linux",
            "ACTIONLINT_TEST_ARCH": "x86_64",
        }
        result = _run_script(
            [str(INSTALL_SCRIPT), "--print-selection"],
            env=env,
        )
        assert result.returncode == 0, f"Harness=1 should authorize overrides: {result.stderr}"


# ===========================================================================
# BT3-03: Harnessed override retains verification
# ===========================================================================


class TestBT303HarnessedOverrideRetainsVerification:
    """With ACTIONLINT_TEST_HARNESS=1, prove controlled URL/digest seams work
    but checksum and exact-version verification still execute."""

    def test_harnessed_url_override_still_verifies_checksum(self, tmp_path: Path) -> None:
        """A harnessed URL pointing to wrong content must still fail checksum."""
        fake_tarball = _make_valid_tarball(tmp_path, "actionlint_1.7.12_linux_amd64.tar.gz", "fake")
        result = _run_script(
            [str(INSTALL_SCRIPT), str(tmp_path / "installdir")],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": f"file://{fake_tarball}",
                # Real expected SHA so the fake content mismatches
            },
        )
        assert result.returncode != 0, "Checksum must still execute even with harness overrides"
        assert "SHA-256 mismatch" in result.stderr or "mismatch" in result.stderr.lower()

    def test_harnessed_sha_override_still_verifies_version(self, tmp_path: Path) -> None:
        """A harnessed SHA override that passes checksum but wrong version must
        still fail version verification."""
        wrong_version_script = '#!/usr/bin/env bash\necho "1.7.120"\n'
        fake_tarball = _make_valid_tarball(
            tmp_path / "sub1", "actionlint_1.7.12_linux_amd64.tar.gz", wrong_version_script
        )
        actual_sha = hashlib.sha256(fake_tarball.read_bytes()).hexdigest()
        result = _run_script(
            [str(INSTALL_SCRIPT), str(tmp_path / "installdir")],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": f"file://{fake_tarball}",
                "ACTIONLINT_TEST_SHA256": actual_sha,
            },
        )
        assert result.returncode != 0, "Version must still be verified even with harness overrides"
        assert "version mismatch" in result.stderr.lower() or "version" in result.stderr.lower()


# ===========================================================================
# BT3-04: Exact version matching
# ===========================================================================


class TestBT304ExactVersionMatching:
    """Prove the real candidate-validation path accepts the genuine expected
    version and rejects 1.7.120, prefix-1.7.12, 1.7.12-malicious, malformed,
    empty, and failing outputs."""

    @pytest.mark.parametrize(
        "version_output,should_accept",
        [
            ("1.7.12\nhttps://github.com/rhysd/actionlint\n", True),
            ("1.7.120\n", False),
            ("prefix-1.7.12\n", False),
            ("1.7.12-malicious\n", False),
            ("1.7.12.0\n", False),
            ("", False),
            ("malformed output\n", False),
            ("1.7.12 \n", True),  # trailing space trimmed
            (" 1.7.12\n", True),  # leading space trimmed
        ],
        ids=[
            "genuine",
            "1.7.120",
            "prefix",
            "malicious-suffix",
            "extra-dot",
            "empty",
            "malformed",
            "trailing-space",
            "leading-space",
        ],
    )
    def test_version_acceptance(
        self, version_output: str, should_accept: bool, tmp_path: Path
    ) -> None:
        """Test the exact version parser against various outputs."""
        # Build a fake tarball with a script outputting the given version
        escaped = version_output.replace("\\", "\\\\").replace("'", "'\\''")
        script_content = f"""#!/usr/bin/env bash
printf '{escaped}'
"""
        # For the empty case, the binary outputs nothing
        if version_output == "":
            script_content = "#!/usr/bin/env bash\ntrue\n"

        fake_tarball = _make_valid_tarball(
            tmp_path / f"v_{hash(version_output)}",
            "actionlint_1.7.12_linux_amd64.tar.gz",
            script_content,
        )
        actual_sha = hashlib.sha256(fake_tarball.read_bytes()).hexdigest()
        result = _run_script(
            [str(INSTALL_SCRIPT), str(tmp_path / "installdir")],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": f"file://{fake_tarball}",
                "ACTIONLINT_TEST_SHA256": actual_sha,
            },
        )
        if should_accept:
            # Should succeed — accepted and installed
            assert result.returncode == 0, (
                f"Version output {version_output!r} should be accepted: {result.stderr}"
            )
        else:
            assert result.returncode != 0, f"Version output {version_output!r} should be rejected"
            assert "version" in result.stderr.lower()

    def test_command_failure_rejected(self, tmp_path: Path) -> None:
        """A candidate where -version exits nonzero must be rejected."""
        script_content = "#!/usr/bin/env bash\nexit 1\n"
        fake_tarball = _make_valid_tarball(
            tmp_path / "cmdfail",
            "actionlint_1.7.12_linux_amd64.tar.gz",
            script_content,
        )
        actual_sha = hashlib.sha256(fake_tarball.read_bytes()).hexdigest()
        result = _run_script(
            [str(INSTALL_SCRIPT), str(tmp_path / "installdir")],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": f"file://{fake_tarball}",
                "ACTIONLINT_TEST_SHA256": actual_sha,
            },
        )
        assert result.returncode != 0


# ===========================================================================
# BT3-05: Rejected candidate is never installed
# ===========================================================================


class TestBT305RejectedCandidateNeverInstalled:
    """For checksum and version rejection, assert no new final binary or
    staging file remains; also prove an existing trusted binary is unchanged."""

    def test_checksum_rejection_leaves_no_binary(self, tmp_path: Path) -> None:
        """Checksum mismatch must not leave any file in install dir."""
        install_dir = tmp_path / "installdir"
        fake_tarball = _make_valid_tarball(
            tmp_path / "cs", "actionlint_1.7.12_linux_amd64.tar.gz", "fake"
        )
        result = _run_script(
            [str(INSTALL_SCRIPT), str(install_dir)],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": f"file://{fake_tarball}",
                # Real SHA so it mismatches
            },
        )
        assert result.returncode != 0
        # No actionlint binary in install dir
        assert not install_dir.exists() or not (install_dir / "actionlint").exists()
        # No staging temp files
        if install_dir.exists():
            leftovers = list(install_dir.iterdir())
            assert len(leftovers) == 0, f"Unexpected files in install dir: {leftovers}"

    def test_version_rejection_leaves_no_binary(self, tmp_path: Path) -> None:
        """Version mismatch must not leave any file in install dir."""
        install_dir = tmp_path / "installdir"
        wrong_version_script = '#!/usr/bin/env bash\necho "1.7.120"\n'
        fake_tarball = _make_valid_tarball(
            tmp_path / "ver", "actionlint_1.7.12_linux_amd64.tar.gz", wrong_version_script
        )
        actual_sha = hashlib.sha256(fake_tarball.read_bytes()).hexdigest()
        result = _run_script(
            [str(INSTALL_SCRIPT), str(install_dir)],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": f"file://{fake_tarball}",
                "ACTIONLINT_TEST_SHA256": actual_sha,
            },
        )
        assert result.returncode != 0
        assert not install_dir.exists() or not (install_dir / "actionlint").exists()

    def test_existing_trusted_binary_unchanged_on_rejection(self, tmp_path: Path) -> None:
        """An existing trusted binary must remain unchanged when a candidate
        is rejected."""
        install_dir = tmp_path / "installdir"
        install_dir.mkdir()

        # Place a pre-existing trusted binary
        trusted_bin = install_dir / "actionlint"
        trusted_content = "#!/usr/bin/env bash\necho 'trusted-binary'\n"
        trusted_bin.write_text(trusted_content)
        trusted_bin.chmod(0o755)
        trusted_hash = hashlib.sha256(trusted_bin.read_bytes()).hexdigest()

        # Attempt install with wrong checksum
        fake_tarball = _make_valid_tarball(
            tmp_path / "exist", "actionlint_1.7.12_linux_amd64.tar.gz", "fake"
        )
        result = _run_script(
            [str(INSTALL_SCRIPT), str(install_dir)],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": f"file://{fake_tarball}",
            },
        )
        assert result.returncode != 0

        # The trusted binary must be unchanged
        assert trusted_bin.exists(), "Existing trusted binary must not be deleted"
        actual_hash = hashlib.sha256(trusted_bin.read_bytes()).hexdigest()
        assert actual_hash == trusted_hash, (
            "Existing trusted binary content must be unchanged on rejection"
        )


# ===========================================================================
# BT3-06: Atomic successful replacement
# ===========================================================================


class TestBT306AtomicSuccessfulReplacement:
    """Prove a valid candidate is installed only after validation and
    atomically replaces the destination with correct executable permissions."""

    def test_valid_candidate_installed_atomically(self, tmp_path: Path) -> None:
        """A valid candidate (correct checksum + version) must be installed
        at the final path with executable permissions."""
        install_dir = tmp_path / "installdir"
        genuine_script = '#!/usr/bin/env bash\necho "1.7.12"\n'
        fake_tarball = _make_valid_tarball(
            tmp_path / "atom", "actionlint_1.7.12_linux_amd64.tar.gz", genuine_script
        )
        actual_sha = hashlib.sha256(fake_tarball.read_bytes()).hexdigest()
        result = _run_script(
            [str(INSTALL_SCRIPT), str(install_dir)],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": f"file://{fake_tarball}",
                "ACTIONLINT_TEST_SHA256": actual_sha,
            },
        )
        assert result.returncode == 0, (
            f"Valid candidate should install successfully: {result.stderr}"
        )
        installed = install_dir / "actionlint"
        assert installed.exists(), "Binary must exist at final path"
        # Must be executable
        perms = stat.S_IMODE(installed.stat().st_mode)
        assert perms & stat.S_IXUSR, f"Installed binary must be executable, got perms {oct(perms)}"
        # No staging temp files left behind
        leftovers = [f for f in install_dir.iterdir() if f.name != "actionlint"]
        assert len(leftovers) == 0, f"Unexpected staging files: {leftovers}"

    def test_replacement_of_existing_binary(self, tmp_path: Path) -> None:
        """Replacing an existing trusted binary must succeed atomically."""
        install_dir = tmp_path / "installdir"
        install_dir.mkdir()
        old_bin = install_dir / "actionlint"
        old_bin.write_text("#!/usr/bin/env bash\necho 'old'\n")
        old_bin.chmod(0o755)

        genuine_script = '#!/usr/bin/env bash\necho "1.7.12"\n'
        fake_tarball = _make_valid_tarball(
            tmp_path / "repl", "actionlint_1.7.12_linux_amd64.tar.gz", genuine_script
        )
        actual_sha = hashlib.sha256(fake_tarball.read_bytes()).hexdigest()
        result = _run_script(
            [str(INSTALL_SCRIPT), str(install_dir)],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": f"file://{fake_tarball}",
                "ACTIONLINT_TEST_SHA256": actual_sha,
            },
        )
        assert result.returncode == 0
        new_content = old_bin.read_text()
        assert "1.7.12" in new_content, "Binary should be replaced with new content"


# ===========================================================================
# BT3-07: Local deterministic download failure
# ===========================================================================


class TestBT307LocalDeterministicDownloadFailure:
    """Use a controlled local curl shim that exits nonzero; prove the real
    installer fails without external network access."""

    def test_failing_curl_shim_rejected(self, tmp_path: Path) -> None:
        """A failing curl shim must cause the installer to fail closed."""
        shim = _make_failing_curl_shim(tmp_path)
        result = _run_script(
            [str(INSTALL_SCRIPT), str(tmp_path / "installdir")],
            env={
                "ACTIONLINT_TEST_HARNESS": "1",
                "ACTIONLINT_TEST_OS": "Linux",
                "ACTIONLINT_TEST_ARCH": "x86_64",
                "ACTIONLINT_TEST_URL": "file:///nonexistent/path.tar.gz",
                "ACTIONLINT_TEST_CURL": str(shim),
            },
        )
        assert result.returncode != 0, "Failing curl shim must cause nonzero exit"
        assert "download" in result.stderr.lower() or "fail" in result.stderr.lower()

    def test_file_url_to_nonexistent_path_fails(self, tmp_path: Path) -> None:
        """A file:// URL to a nonexistent path must fail (no external network)."""
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
# BT3-08: Non-skippable missing uv
# ===========================================================================


class TestBT308NonSkippableMissingUv:
    """Use a temporary controlled PATH that contains needed commands but
    excludes uv; prove run_workflow_lint.sh always executes and fails nonzero
    without pytest.skip."""

    def test_missing_uv_always_fails(self, tmp_path: Path) -> None:
        """run_workflow_lint.sh must fail nonzero in a controlled PATH
        without uv — no skip allowed."""
        # Build a controlled PATH with bash, curl, sha256sum, tar, make
        # but explicitly excluding uv
        controlled_bin = tmp_path / "bin"
        controlled_bin.mkdir()

        # Create symlinks to needed commands
        needed = [
            "bash",
            "curl",
            "tar",
            "sha256sum",
            "shasum",
            "make",
            "git",
            "awk",
            "sed",
            "grep",
            "mkdir",
            "rm",
            "cp",
            "mv",
            "chmod",
            "head",
            "command",
            "dirname",
            "pwd",
            "cat",
            "echo",
            "mktemp",
        ]
        for cmd in needed:
            path = subprocess.run(
                ["bash", "-c", f"command -v {cmd} 2>/dev/null"],
                capture_output=True,
                text=True,
            ).stdout.strip()
            if path:
                link = controlled_bin / cmd
                if not link.exists():
                    link.symlink_to(path)

        controlled_path = str(controlled_bin)

        # Verify uv is NOT on this path
        uv_check = subprocess.run(
            ["bash", "-c", f'PATH="{controlled_path}" command -v uv 2>/dev/null'],
            capture_output=True,
            text=True,
        )
        assert not uv_check.stdout.strip(), "Test setup error: uv found on controlled PATH"

        result = subprocess.run(
            ["bash", str(RUN_LINT_SCRIPT)],
            capture_output=True,
            text=True,
            env={
                "PATH": controlled_path,
                "HOME": os.environ.get("HOME", "/tmp"),
            },
            cwd=str(REPO_ROOT),
            timeout=30,
        )
        assert result.returncode != 0, "Missing uv must always fail closed — no skip allowed"
        assert "uv" in result.stderr.lower()
