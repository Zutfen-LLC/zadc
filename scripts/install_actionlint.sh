#!/usr/bin/env bash
# Deterministically install actionlint v1.7.12 to the local bin directory.
#
# Downloads the exact v1.7.12 GitHub release asset selected by a committed
# platform manifest, verifies its SHA-256 against a committed trusted digest,
# extracts the binary, and verifies it reports the exact expected release
# version before declaring success.
#
# Supported host tuples (uname -s / uname -m):
#   linux/x86_64  linux/aarch64  darwin/x86_64  darwin/arm64
#
# Fails closed (nonzero exit) on: unsupported OS/architecture, unknown
# mapping, download failure, checksum mismatch, extraction failure, missing
# required utilities, or version mismatch.
#
# Usage:
#   scripts/install_actionlint.sh [install-dir]
#   scripts/install_actionlint.sh --print-selection   (test/diagnostic: no download)
#
# Test-only environment overrides (rejected when CI=true unless
# ACTIONLINT_TEST_HARNESS=1 is also set):
#   ACTIONLINT_TEST_OS     — override OS detection (e.g. "Linux", "Darwin")
#   ACTIONLINT_TEST_ARCH   — override arch detection (e.g. "x86_64", "aarch64")
#   ACTIONLINT_TEST_URL    — override download URL (e.g. file:// fixture)
#   ACTIONLINT_TEST_SHA256 — override expected SHA-256 digest
#
# These overrides NEVER weaken checksum or version verification — both checks
# always execute regardless of overrides.  They only change what is downloaded
# and what digest is expected, so that negative-path tests can prove each
# verification layer independently.
#
# All progress messages go to stderr; only the install directory path goes to
# stdout (for $() capture and GITHUB_PATH appending).

set -euo pipefail

ACTIONLINT_VERSION="1.7.12"
RELEASE_BASE="https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Test-seam guard: overrides are rejected in CI/production unless the test
# harness explicitly enables them.
# ---------------------------------------------------------------------------
_test_overrides_allowed() {
    if [ "${CI:-}" = "true" ] && [ "${ACTIONLINT_TEST_HARNESS:-}" != "1" ]; then
        return 1
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
detect_os() {
    if _test_overrides_allowed && [ -n "${ACTIONLINT_TEST_OS:-}" ]; then
        echo "$ACTIONLINT_TEST_OS"
    else
        uname -s
    fi
}

detect_arch() {
    if _test_overrides_allowed && [ -n "${ACTIONLINT_TEST_ARCH:-}" ]; then
        echo "$ACTIONLINT_TEST_ARCH"
    else
        uname -m
    fi
}

# ---------------------------------------------------------------------------
# Normalize common uname aliases to canonical actionlint identifiers
# ---------------------------------------------------------------------------
normalize_os() {
    local raw="$1"
    case "$raw" in
        [Ll]inux)   echo "linux" ;;
        [Dd]arwin)  echo "darwin" ;;
        *)          echo "$raw" ;;
    esac
}

normalize_arch() {
    local raw="$1"
    case "$raw" in
        x86_64|amd64)   echo "amd64" ;;
        aarch64|arm64)  echo "arm64" ;;
        *)              echo "$raw" ;;
    esac
}

# ---------------------------------------------------------------------------
# Platform manifest: sets ASSET_FILENAME and EXPECTED_SHA256 for the given
# normalized "os arch" pair.
#
# SHA-256 values sourced from the official v1.7.12 release checksums file:
#   https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_checksums.txt
# ---------------------------------------------------------------------------
ASSET_FILENAME=""
EXPECTED_SHA256=""

select_platform() {
    local os="$1" arch="$2"
    local key="${os}:${arch}"
    case "$key" in
        linux:amd64)
            ASSET_FILENAME="actionlint_${ACTIONLINT_VERSION}_linux_amd64.tar.gz"
            EXPECTED_SHA256="8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"
            ;;
        linux:arm64)
            ASSET_FILENAME="actionlint_${ACTIONLINT_VERSION}_linux_arm64.tar.gz"
            EXPECTED_SHA256="325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6"
            ;;
        darwin:amd64)
            ASSET_FILENAME="actionlint_${ACTIONLINT_VERSION}_darwin_amd64.tar.gz"
            EXPECTED_SHA256="5b44c3bc2255115c9b69e30efc0fecdf498fdb63c5d58e17084fd5f16324c644"
            ;;
        darwin:arm64)
            ASSET_FILENAME="actionlint_${ACTIONLINT_VERSION}_darwin_arm64.tar.gz"
            EXPECTED_SHA256="aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f"
            ;;
        *)
            echo "FAIL: Unsupported host tuple: ${os}/${arch}" >&2
            echo "  Supported: linux/amd64, linux/arm64, darwin/amd64, darwin/arm64" >&2
            echo "  Detected OS:   ${os}" >&2
            echo "  Detected arch: ${arch}" >&2
            return 1
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Checksum helper (works on Linux with sha256sum and macOS with shasum)
# ---------------------------------------------------------------------------
compute_sha256() {
    local file="$1"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$file" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$file" | awk '{print $1}'
    else
        echo "FAIL: Neither sha256sum nor shasum found on PATH" >&2
        return 1
    fi
}

# ---------------------------------------------------------------------------
# --print-selection: output "asset_filename sha256" for the detected platform
# without downloading. Used by behavioral tests (BT-01, BT-02).
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--print-selection" ]; then
    RAW_OS="$(detect_os)"
    RAW_ARCH="$(detect_arch)"
    OS="$(normalize_os "$RAW_OS")"
    ARCH="$(normalize_arch "$RAW_ARCH")"
    select_platform "$OS" "$ARCH" || exit 1
    echo "${ASSET_FILENAME} ${EXPECTED_SHA256}"
    exit 0
fi

# ===========================================================================
# Main provisioning flow
# ===========================================================================

INSTALL_DIR="${1:-$REPO_ROOT/.tools/bin}"

# --- Verify required utilities ---
for util in curl tar; do
    if ! command -v "$util" >/dev/null 2>&1; then
        echo "FAIL: Required utility '$util' not found on PATH" >&2
        exit 1
    fi
done
if ! command -v sha256sum >/dev/null 2>&1 && ! command -v shasum >/dev/null 2>&1; then
    echo "FAIL: Required checksum utility (sha256sum or shasum) not found on PATH" >&2
    exit 1
fi

# --- Detect platform and select asset from committed manifest ---
RAW_OS="$(detect_os)"
RAW_ARCH="$(detect_arch)"
OS="$(normalize_os "$RAW_OS")"
ARCH="$(normalize_arch "$RAW_ARCH")"

echo "[install_actionlint] Detected platform: ${OS}/${ARCH} (raw: ${RAW_OS}/${RAW_ARCH})" >&2

select_platform "$OS" "$ARCH" || exit 1

echo "[install_actionlint] Selected asset: ${ASSET_FILENAME}" >&2
echo "[install_actionlint] Expected SHA-256: ${EXPECTED_SHA256}" >&2

# --- Apply test-only overrides (never in production CI) ---
DOWNLOAD_URL="${RELEASE_BASE}/${ASSET_FILENAME}"
if _test_overrides_allowed && [ -n "${ACTIONLINT_TEST_URL:-}" ]; then
    DOWNLOAD_URL="$ACTIONLINT_TEST_URL"
    echo "[install_actionlint] TEST MODE: Using override download URL" >&2
fi

if _test_overrides_allowed && [ -n "${ACTIONLINT_TEST_SHA256:-}" ]; then
    EXPECTED_SHA256="$ACTIONLINT_TEST_SHA256"
    echo "[install_actionlint] TEST MODE: Using override SHA-256" >&2
fi

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

# --- Download ---
echo "[install_actionlint] Downloading from ${DOWNLOAD_URL}..." >&2
TARBALL_PATH="${TMPDIR}/${ASSET_FILENAME}"
if ! curl -fsSL -o "$TARBALL_PATH" "$DOWNLOAD_URL"; then
    echo "FAIL: Could not download actionlint from ${DOWNLOAD_URL}" >&2
    exit 1
fi

# --- Verify SHA-256 (before extraction or execution) ---
echo "[install_actionlint] Verifying SHA-256..." >&2
ACTUAL_SHA256="$(compute_sha256 "$TARBALL_PATH")" || exit 1
if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
    echo "FAIL: actionlint SHA-256 mismatch" >&2
    echo "  expected: $EXPECTED_SHA256" >&2
    echo "  actual:   $ACTUAL_SHA256" >&2
    exit 1
fi
echo "[install_actionlint] SHA-256 verified: $ACTUAL_SHA256" >&2

# --- Extract ---
mkdir -p "$INSTALL_DIR"
if ! tar -xzf "$TARBALL_PATH" -C "$TMPDIR" actionlint; then
    echo "FAIL: Could not extract actionlint binary from tarball" >&2
    exit 1
fi

cp "$TMPDIR/actionlint" "$INSTALL_DIR/actionlint"
chmod +x "$INSTALL_DIR/actionlint"

# --- Verify exact release version (defense in depth — before use) ---
echo "[install_actionlint] Verifying actionlint version..." >&2
VERSION_OUTPUT="$("$INSTALL_DIR/actionlint" -version 2>&1 || true)"
if ! echo "$VERSION_OUTPUT" | grep -qF "${ACTIONLINT_VERSION}"; then
    echo "FAIL: actionlint version mismatch" >&2
    echo "  expected: ${ACTIONLINT_VERSION}" >&2
    echo "  actual:   ${VERSION_OUTPUT}" >&2
    exit 1
fi
echo "[install_actionlint] Version verified: ${ACTIONLINT_VERSION}" >&2

echo "[install_actionlint] Installed actionlint to ${INSTALL_DIR}/actionlint" >&2
# Only stdout line: the install directory path
echo "$INSTALL_DIR"
