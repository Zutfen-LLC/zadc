#!/usr/bin/env bash
# Install the repository-local pre-commit hook.
# This hook runs the same quality gate as `make check` and does not require
# a globally installed pre-commit framework.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOKS_DIR="$REPO_ROOT/.githooks"
GIT_HOOK="$HOOKS_DIR/pre-commit"

if [ ! -f "$GIT_HOOK" ]; then
    echo "ERROR: pre-commit hook not found at $GIT_HOOK"
    exit 1
fi

# Configure git to use the local hooks directory
git config core.hooksPath .githooks
chmod +x "$GIT_HOOK"

echo "OK: Pre-commit hook installed. Git core.hooksPath set to .githooks"
echo "The hook runs 'make check' before allowing a commit."
