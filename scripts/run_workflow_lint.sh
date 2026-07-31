#!/usr/bin/env bash
# Run GitHub workflow linting with deterministic, fail-closed tool provisioning.
#
# actionlint: installed via scripts/install_actionlint.sh (pinned v1.7.12,
#   SHA-256 verified + version verified before execution).
#   No PATH or preinstalled fallback — always uses the deterministic installer.
# zizmor: installed via the uv-locked dev environment (pinned >=1.0,<2).
#
# Exits nonzero on any error, missing tool, checksum mismatch, version
# mismatch, or audit failure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKFLOWS_DIR="$REPO_ROOT/.github/workflows"

if [ ! -d "$WORKFLOWS_DIR" ]; then
    echo "FAIL: No .github/workflows directory found" >&2
    exit 1
fi

# --- Fail closed: uv must be available (checked before provisioning) ---
UV_BIN="${UV:-uv}"
if ! command -v "$UV_BIN" >/dev/null 2>&1; then
    echo "FAIL: uv not found. Install uv and run 'make sync'." >&2
    echo "  Install uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

# --- Provision and run actionlint (deterministic, no fallback) ---
# Always use the pinned installer — never trust a preinstalled or PATH binary.
TOOLS_BIN="$(bash "$SCRIPT_DIR/install_actionlint.sh")"
ACTIONLINT_BIN="$TOOLS_BIN/actionlint"

echo "[workflow-lint] Running actionlint ($("$ACTIONLINT_BIN" -version 2>&1 | head -1))..."
if ! "$ACTIONLINT_BIN"; then
    echo "FAIL: actionlint reported errors" >&2
    exit 1
fi
echo "[workflow-lint] actionlint passed"

# --- Run zizmor (pinned via uv dev environment) ---
echo "[workflow-lint] Running zizmor (uv-locked)..."
if ! "$UV_BIN" run zizmor "$WORKFLOWS_DIR"; then
    echo "FAIL: zizmor reported errors" >&2
    exit 1
fi
echo "[workflow-lint] zizmor passed"

# --- Run structural workflow verification ---
echo "[workflow-lint] Running workflow pattern verification..."
if ! bash "$SCRIPT_DIR/verify_workflows.sh"; then
    echo "FAIL: workflow pattern verification failed" >&2
    exit 1
fi

echo "[workflow-lint] All workflow linting passed"
