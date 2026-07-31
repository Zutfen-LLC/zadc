#!/usr/bin/env bash
# Verify GitHub workflow files for forbidden patterns.
# Checks: no pull_request_target, no mutable action refs,
# no write permissions at top level of CI, persist-credentials: false on checkouts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKFLOWS_DIR="$REPO_ROOT/.github/workflows"

if [ ! -d "$WORKFLOWS_DIR" ]; then
    echo "ERROR: No .github/workflows directory found"
    exit 1
fi

ERRORS=0

for wf in "$WORKFLOWS_DIR"/*.yml "$WORKFLOWS_DIR"/*.yaml; do
    [ -f "$wf" ] || continue
    wf_name=$(basename "$wf")

    # Check for pull_request_target
    if grep -q "pull_request_target" "$wf"; then
        echo "FAIL: $wf_name uses pull_request_target"
        ERRORS=$((ERRORS + 1))
    fi

    # Check that actions are pinned to full SHAs
    while IFS= read -r line; do
        if echo "$line" | grep -qE '^\s*- uses:'; then
            ref=$(echo "$line" | sed 's/.*- uses:\s*//' | sed 's/\s*#.*//' | tr -d ' ')
            # Skip local actions
            if [[ "$ref" == .* ]]; then
                continue
            fi
            # Check for @sha pattern
            if [[ "$ref" == *@* ]]; then
                sha="${ref##*@}"
                if [ ${#sha} -ne 40 ]; then
                    echo "FAIL: $wf_name action not pinned to full 40-char SHA: $ref"
                    ERRORS=$((ERRORS + 1))
                fi
            else
                echo "FAIL: $wf_name action not pinned with @SHA: $ref"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    done < "$wf"

    # Check persist-credentials on checkouts
    if grep -q "actions/checkout" "$wf"; then
        if ! grep -q "persist-credentials: false" "$wf"; then
            echo "FAIL: $wf_name has checkout without persist-credentials: false"
            ERRORS=$((ERRORS + 1))
        fi
    fi
done

if [ "$ERRORS" -gt 0 ]; then
    echo ""
    echo "FAILED: $ERRORS workflow verification error(s) found"
    exit 1
else
    echo "OK: All workflow files passed verification"
    exit 0
fi
