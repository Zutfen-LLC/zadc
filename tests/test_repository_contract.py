"""Repository contract tests for ZADC-000.

These tests verify the structural identity, required files, authoritative
design digest, and forbidden patterns required by the packet.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_DESIGN_SHA256 = "d7ffd1a8ad68013a4df43870c9cffc3875f65dd7a16a6eca1f2c6ca7385666cb"


class TestPackageRepositoryNaming:
    """Verify exact package/repository/import/CLI naming from the packet."""

    def test_distribution_name(self) -> None:
        """Pyproject distribution name must be ``zutfen-zadc``."""
        content = REPO_ROOT.joinpath("pyproject.toml").read_text()
        assert 'name = "zutfen-zadc"' in content

    def test_repository_name_in_docs(self) -> None:
        """Repository reference must be ``Zutfen-LLC/zadc``."""
        readme = REPO_ROOT.joinpath("README.md").read_text()
        assert "Zutfen-LLC/zadc" in readme

    def test_import_name_in_pyproject(self) -> None:
        """Package import must be ``zadc``."""
        content = REPO_ROOT.joinpath("pyproject.toml").read_text()
        assert "src/zadc" in content or 'packages = ["src/zadc"]' in content

    def test_cli_command(self) -> None:
        """CLI command must be ``zadc``."""
        content = REPO_ROOT.joinpath("pyproject.toml").read_text()
        assert 'zadc = "zadc.cli:main"' in content


class TestRequiredFoundationFiles:
    """Verify all required foundation files exist."""

    @pytest.mark.parametrize(
        "rel_path",
        [
            "README.md",
            "LICENSE.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "AGENTS.md",
            "NOTICE",
            "pyproject.toml",
            "uv.lock",
            "Makefile",
            ".gitignore",
            ".gitattributes",
            ".editorconfig",
            ".python-version",
            "src/zadc/__init__.py",
            "src/zadc/__main__.py",
            "src/zadc/cli.py",
            "src/zadc/py.typed",
            "tests/test_cli.py",
            "tests/test_package.py",
            "tests/test_repository_contract.py",
            "docs/architecture/ZUTFEN-AGENTIC-DEV-CONTRACT-v0.1.md",
            "docs/governance/bootstrap-trust.md",
            "docs/roadmap.md",
            "docs/releasing.md",
            ".github/workflows/ci.yml",
            ".github/workflows/codeql.yml",
            ".github/dependabot.yml",
            ".github/pull_request_template.md",
            ".github/ISSUE_TEMPLATE/bug_report.yml",
            ".github/ISSUE_TEMPLATE/feature_request.yml",
            "scripts/setup-hooks.sh",
            "scripts/package_smoke.py",
            "scripts/verify_workflows.sh",
            ".githooks/pre-commit",
        ],
    )
    def test_file_exists(self, rel_path: str) -> None:
        f = REPO_ROOT / rel_path
        assert f.exists(), f"Required file missing: {rel_path}"


class TestAuthoritativeDesignDigest:
    """Verify the committed architecture document matches the pinned SHA-256."""

    def test_design_doc_sha256(self) -> None:
        design_path = REPO_ROOT / "docs/architecture/ZUTFEN-AGENTIC-DEV-CONTRACT-v0.1.md"
        content = design_path.read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        assert actual == EXPECTED_DESIGN_SHA256, (
            f"Design document SHA-256 mismatch: expected {EXPECTED_DESIGN_SHA256}, got {actual}"
        )


class TestForbiddenWorkflowPatterns:
    """Verify no forbidden workflow patterns are present."""

    def test_no_pull_request_target(self) -> None:
        """No workflow may use ``pull_request_target``."""
        workflows_dir = REPO_ROOT / ".github/workflows"
        for wf in workflows_dir.glob("*.yml"):
            content = wf.read_text()
            assert "pull_request_target" not in content, (
                f"Workflow {wf.name} uses forbidden pull_request_target"
            )

    def test_no_write_permissions_at_top_level(self) -> None:
        """CI workflow top-level permissions must be ``contents: read`` only."""
        ci_path = REPO_ROOT / ".github/workflows/ci.yml"
        content = ci_path.read_text()
        assert "permissions:" in content
        assert "contents: read" in content
        # Check there's no top-level write permission in CI
        # (CodeQL has a different, narrowly-scoped permission for security-events)
        assert "contents: write" not in content
        assert "pull-requests: write" not in content

    def test_checkouts_persist_credentials_false(self) -> None:
        """Every checkout must set persist-credentials: false."""
        workflows_dir = REPO_ROOT / ".github/workflows"
        for wf in workflows_dir.glob("*.yml"):
            content = wf.read_text()
            # Find all checkout references
            if "actions/checkout" in content:
                assert "persist-credentials: false" in content, (
                    f"Workflow {wf.name} missing persist-credentials: false"
                )

    def test_actions_pinned_to_sha(self) -> None:
        """Every uses: reference must be pinned to a full 40-char SHA."""
        workflows_dir = REPO_ROOT / ".github/workflows"
        for wf in sorted(workflows_dir.glob("*.yml")):
            content = wf.read_text()
            lines = content.splitlines()
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("- uses:"):
                    # Extract the action reference
                    ref = stripped.removeprefix("- uses:").strip()
                    # Remove inline comments
                    ref = ref.split("#")[0].strip()
                    # Skip local actions (./)
                    if ref.startswith("./"):
                        continue
                    # Must be pinned: owner/repo@<40-char-sha>
                    if "@" in ref:
                        sha = ref.rsplit("@", 1)[1]
                        assert len(sha) == 40, (
                            f"Action in {wf.name} not pinned to full SHA: {ref} "
                            f"(sha length {len(sha)})"
                        )
                        assert all(c in "0123456789abcdef" for c in sha.lower()), (
                            f"Action SHA not hex in {wf.name}: {ref}"
                        )
