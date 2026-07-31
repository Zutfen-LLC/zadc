#!/usr/bin/env bash
# Deterministically install actionlint v1.7.12 to the local bin directory.
#
# Downloads the exact release tarball, verifies its SHA-256 against a committed
# digest, and extracts the binary.  Fails closed on any error: network failure,
# checksum mismatch, or extraction failure all produce a nonzero exit.
#
# Usage:
#   scripts/install_actionlint.sh [install-dir]
#
# If install-dir is omitted, the binary is placed in .tools/bin/ and that
# directory is printed to stdout (last line) for PATH addition.
# All progress messages go to stderr.

set -euo pipefail

ACTIONLINT_VERSION="1.7.12"
ACTIONLINT_TARBALL="actionlint_${ACTIONLINT_VERSION}_linux_amd64.tar.gz"
ACTIONLINT_URL="https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/${ACTIONLINT_TARBALL}"
ACTIONLINT_SHA256="8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALL_DIR="${1:-$REPO_ROOT/.tools/bin}"

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

echo "[install_actionlint] Downloading actionlint v${ACTIONLINT_VERSION}..." >&2
TARBALL_PATH="${TMPDIR}/${ACTIONLINT_TARBALL}"
if ! curl -fsSL -o "$TARBALL_PATH" "$ACTIONLINT_URL"; then
    echo "FAIL: Could not download actionlint from $ACTIONLINT_URL" >&2
    exit 1
fi

echo "[install_actionlint] Verifying SHA-256..." >&2
ACTUAL_SHA256="$(sha256sum "$TARBALL_PATH" | awk '{print $1}')"
if [ "$ACTUAL_SHA256" != "$ACTIONLINT_SHA256" ]; then
    echo "FAIL: actionlint SHA-256 mismatch" >&2
    echo "  expected: $ACTIONLINT_SHA256" >&2
    echo "  actual:   $ACTUAL_SHA256" >&2
    exit 1
fi
echo "[install_actionlint] SHA-256 verified: $ACTUAL_SHA256" >&2

mkdir -p "$INSTALL_DIR"
if ! tar -xzf "$TARBALL_PATH" -C "$TMPDIR" actionlint; then
    echo "FAIL: Could not extract actionlint binary" >&2
    exit 1
fi

cp "$TMPDIR/actionlint" "$INSTALL_DIR/actionlint"
chmod +x "$INSTALL_DIR/actionlint"

echo "[install_actionlint] Installed actionlint to $INSTALL_DIR/actionlint" >&2
# Only stdout line: the install directory path
echo "$INSTALL_DIR"
