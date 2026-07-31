"""Repository contract tests for ZADC-000.

These tests verify the structural identity, required files, authoritative
design digest, roadmap sequence, exact-head CI contract, deterministic tool
pins, fail-closed workflow-lint, and fail-closed pre-commit hook.
"""

from __future__ import annotations

import hashlib
import re
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
            "scripts/install_actionlint.sh",
            "scripts/run_workflow_lint.sh",
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


class TestRoadmapSequence:
    """Regression test: roadmap must match the authoritative slice sequence."""

    EXPECTED_SEQUENCE = [
        ("ZADC-000", "Universal Repository Bootstrap"),
        ("ZADC-001A", "Canonical artifacts and rendering"),
        ("ZADC-001B", "Workflow bundles and derived lifecycle"),
        ("ZADC-001C", "Git subject and evidence validation"),
        ("ZADC-001D", "GitHub and GitHub Actions reconciliation"),
        ("ZADC-001E", "Review, correction, and human-decision workflow"),
        ("ZADC-001F", "First live project dogfood"),
        ("ZADC-002", "Engram provenance integration"),
        ("ZADC-003", "Flowstate orchestration integration"),
    ]

    def test_roadmap_contains_exact_sequence(self) -> None:
        """The roadmap headings must match the authorized sequence exactly."""
        roadmap = (REPO_ROOT / "docs/roadmap.md").read_text()
        for slice_id, title_fragment in self.EXPECTED_SEQUENCE:
            # Each slice ID must appear as a heading
            assert slice_id in roadmap, f"Roadmap missing required slice: {slice_id}"
            # The title fragment must appear on the same heading line
            heading_h3 = f"### {slice_id} — {title_fragment}"
            heading_h2 = f"## {slice_id} — {title_fragment}"
            assert heading_h3 in roadmap or heading_h2 in roadmap, (
                f"Roadmap heading for {slice_id} must match: '{title_fragment}'"
            )

    def test_roadmap_preserves_order(self) -> None:
        """Slice IDs must appear in the correct order in the roadmap."""
        roadmap = (REPO_ROOT / "docs/roadmap.md").read_text()
        positions: list[int] = []
        for slice_id, _ in self.EXPECTED_SEQUENCE:
            pos = roadmap.find(slice_id)
            assert pos >= 0, f"Slice {slice_id} not found in roadmap"
            positions.append(pos)
        for i in range(1, len(positions)):
            assert positions[i] > positions[i - 1], (
                f"Roadmap order violation: "
                f"{self.EXPECTED_SEQUENCE[i][0]} appears before "
                f"{self.EXPECTED_SEQUENCE[i - 1][0]}"
            )


class TestExactHeadWorkflowContract:
    """Verify CI and CodeQL checkout and assert the exact PR source-head SHA."""

    def _read_ci(self) -> str:
        return (REPO_ROOT / ".github/workflows/ci.yml").read_text()

    def _read_codeql(self) -> str:
        return (REPO_ROOT / ".github/workflows/codeql.yml").read_text()

    def test_ci_checkouts_pr_head_sha(self) -> None:
        """CI must use github.event.pull_request.head.sha for PR checkouts."""
        ci = self._read_ci()
        assert "github.event.pull_request.head.sha" in ci, (
            "CI must checkout the exact PR source-head SHA"
        )

    def test_ci_preserves_required_context_names(self) -> None:
        """Required CI context names must be preserved exactly."""
        ci = self._read_ci()
        required_names = [
            "name: workflow-lint",
            "name: quality",
            'name: "test (${{ matrix.python-version }})"',
            "name: package",
        ]
        for name in required_names:
            assert name in ci, f"Required context name missing in ci.yml: {name}"

    def test_ci_matrix_versions_preserved(self) -> None:
        """CI test matrix must cover 3.11 through 3.14."""
        ci = self._read_ci()
        for version in ["3.11", "3.12", "3.13", "3.14"]:
            assert f'"{version}"' in ci, f"Python {version} missing from CI matrix"

    def test_every_ci_job_asserts_head_sha(self) -> None:
        """Every CI job must assert git rev-parse HEAD matches expected SHA."""
        ci = self._read_ci()
        # Count checkout steps that use the exact PR head ref
        checkout_ref_count = len(re.findall(r"ref: .*github\.event\.pull_request\.head\.sha", ci))
        assert_count = ci.count("Assert checked-out HEAD matches event subject SHA")
        assert assert_count == checkout_ref_count, (
            f"Expected {checkout_ref_count} SHA assertions in ci.yml, found {assert_count}"
        )

    def test_codeql_checkouts_pr_head_sha(self) -> None:
        """CodeQL must use github.event.pull_request.head.sha for PR checkouts."""
        codeql = self._read_codeql()
        assert "github.event.pull_request.head.sha" in codeql, (
            "CodeQL must checkout the exact PR source-head SHA"
        )

    def test_codeql_asserts_head_sha(self) -> None:
        """CodeQL must assert git rev-parse HEAD matches expected SHA."""
        codeql = self._read_codeql()
        assert "Assert checked-out HEAD matches event subject SHA" in codeql, (
            "CodeQL must assert the checked-out HEAD SHA"
        )


class TestDeterministicToolPins:
    """Verify actionlint, zizmor, and uv are pinned deterministically."""

    def test_actionlint_install_script_has_pinned_version(self) -> None:
        """The actionlint install script must pin an exact version."""
        script = (REPO_ROOT / "scripts/install_actionlint.sh").read_text()
        assert 'ACTIONLINT_VERSION="1.7.12"' in script, (
            "actionlint version must be pinned to 1.7.12"
        )

    def test_actionlint_install_script_has_sha256(self) -> None:
        """The actionlint install script must verify committed SHA-256 values
        from the platform manifest."""
        script = (REPO_ROOT / "scripts/install_actionlint.sh").read_text()
        assert "EXPECTED_SHA256" in script, (
            "actionlint install must use committed SHA-256 digests from manifest"
        )
        assert "sha256sum" in script or "shasum" in script, (
            "actionlint install must run checksum verification"
        )

    def test_no_mutable_actionlint_download(self) -> None:
        """CI must not download actionlint from a mutable branch ref."""
        ci = (REPO_ROOT / ".github/workflows/ci.yml").read_text()
        assert "download-actionlint.bash" not in ci, (
            "CI must not use the mutable actionlint download script"
        )
        assert "install_actionlint.sh" in ci, (
            "CI must use the deterministic install_actionlint.sh script"
        )

    def test_zizmor_via_uv_locked(self) -> None:
        """zizmor must be installed via the uv-locked dev environment."""
        ci = (REPO_ROOT / ".github/workflows/ci.yml").read_text()
        assert "uv run zizmor" in ci, "CI must run zizmor via uv run"
        assert "cargo install zizmor" not in ci, "CI must not use mutable cargo install for zizmor"
        assert "pip install zizmor" not in ci, "CI must not use mutable pip install for zizmor"

    def test_zizmor_in_pyproject_dev(self) -> None:
        """zizmor must be listed as a dev dependency in pyproject.toml."""
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        assert "zizmor" in pyproject, "zizmor must be in dev dependencies"

    def test_uv_pinned_in_ci(self) -> None:
        """setup-uv must pin an exact version, not latest."""
        ci = (REPO_ROOT / ".github/workflows/ci.yml").read_text()
        assert 'version: "0.8.13"' in ci, "setup-uv must pin an exact version (0.8.13)"

    def test_workflow_lint_script_exists(self) -> None:
        """The deterministic workflow-lint runner script must exist."""
        assert (REPO_ROOT / "scripts/run_workflow_lint.sh").exists(), (
            "scripts/run_workflow_lint.sh must exist"
        )


class TestFailClosedWorkflowLint:
    """Verify make workflow-lint fails closed (no warning-and-skip paths)."""

    def test_makefile_workflow_lint_no_skip(self) -> None:
        """Makefile workflow-lint must not contain warning-and-skip logic."""
        makefile = (REPO_ROOT / "Makefile").read_text()
        assert "WARNING" not in makefile, "Makefile must not contain warning-and-skip paths"
        assert "skipping" not in makefile.lower(), (
            "Makefile must not contain skip paths in workflow-lint"
        )

    def test_run_workflow_lint_script_fails_on_missing_tool(self) -> None:
        """The workflow-lint script must exit nonzero when a tool is missing."""
        script = (REPO_ROOT / "scripts/run_workflow_lint.sh").read_text()
        assert "exit 1" in script, "run_workflow_lint.sh must have nonzero exit on failure"
        assert "FAIL:" in script or "exit 1" in script

    def test_no_preinstalled_actionlint_fallback(self) -> None:
        """The workflow-lint script must not fall back to a preinstalled or
        PATH actionlint binary. It must always use the deterministic installer."""
        script = (REPO_ROOT / "scripts/run_workflow_lint.sh").read_text()
        assert "fall back" not in script.lower(), (
            "run_workflow_lint.sh must not contain fallback language"
        )
        assert "pre-installed" not in script.lower(), (
            "run_workflow_lint.sh must not use pre-installed actionlint"
        )
        # Must always call the deterministic installer
        assert "install_actionlint.sh" in script, (
            "run_workflow_lint.sh must use install_actionlint.sh"
        )


class TestFailClosedPreCommit:
    """Verify the installed pre-commit hook fails closed when uv is absent."""

    def test_pre_commit_fails_closed_on_missing_uv(self) -> None:
        """The pre-commit hook must exit nonzero when uv is not found."""
        hook = (REPO_ROOT / ".githooks/pre-commit").read_text()
        assert "uv" in hook
        # Must NOT contain the old warning-and-skip behavior
        assert "WARNING: uv not found. Skipping checks." not in hook, (
            "Pre-commit hook must not silently skip when uv is missing"
        )
        # Must contain a fail-closed exit when uv is unavailable
        assert "exit 1" in hook, "Pre-commit hook must exit nonzero on missing uv"
