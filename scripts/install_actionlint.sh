#!/usr/bin/env bash
# Deterministically install actionlint v1.7.12 to the local bin directory.
#
# Downloads the exact v1.7.12 GitHub release asset selected by a committed
# platform manifest, verifies its SHA-256 against a committed trusted digest,
# extracts the binary to a temporary staging area, validates the candidate's
# exact version, and then atomically installs it.
#
# Supported host tuples (uname -s / uname -m):
#   linux/x86_64  linux/aarch64  darwin/x86_64  darwin/arm64
#
# Fails closed (nonzero exit) on: unsupported OS/architecture, unknown
# mapping, download failure, checksum mismatch, extraction failure, missing
# required utilities, or version mismatch.
#
# Atomic install: the candidate is validated in staging before the final
# path is touched.  On failure, any previously trusted binary remains
# unchanged and no staging remnants are left in the install directory.
#
# Usage:
#   scripts/install_actionlint.sh [install-dir]
#   scripts/install_actionlint.sh --print-selection   (test/diagnostic: no download)
#
# Test-only environment overrides (accepted ONLY when ACTIONLINT_TEST_HARNESS
# is set to the exact string "1"):
#   ACTIONLINT_TEST_OS     — override OS detection (e.g. "Linux", "Darwin")
#   ACTIONLINT_TEST_ARCH   — override arch detection (e.g. "x86_64", "aarch64")
#   ACTIONLINT_TEST_URL    — override download URL (e.g. file:// fixture)
#   ACTIONLINT_TEST_SHA256 — override expected SHA-256 digest
#   ACTIONLINT_TEST_CURL   — override curl binary path (test shim)
#
# Any override variable set without ACTIONLINT_TEST_HARNESS=1 causes immediate
# failure before platform selection, download, extraction, or execution.
# ACTIONLINT_TEST_HARNESS values other than the exact string "1" do not
# authorize overrides.
#
# These overrides NEVER weaken checksum or exact-version verification — both
# checks always execute regardless of overrides.
#
# All progress messages go to stderr; only the install directory path goes to
# stdout (for $() capture and GITHUB_PATH appending).

set -euo pipefail

ACTIONLINT_VERSION="1.7.12"
RELEASE_BASE="https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# -----------------------------------------------------------------------
# FIX3-A: Test-seam gate — overrides require ACTIONLINT_TEST_HARNESS=1
# exactly.  The gate is environment-independent: CI=true is not the
# deciding factor.  Any override variable present without the exact
# harness value causes immediate failure.
# -----------------------------------------------------------------------

# List of all test override variables that require the harness.
_TEST_OVERRIDE_VARS=(
    ACTIONLINT_TEST_OS
    ACTIONLINT_TEST_ARCH
    ACTIONLINT_TEST_URL
    ACTIONLINT_TEST_SHA256
    ACTIONLINT_TEST_CURL
)

# Returns 0 (true) if ACTIONLINT_TEST_HARNESS is exactly "1".
_harness_active() {
    [ "${ACTIONLINT_TEST_HARNESS:-}" = "1" ]
}

# Check for stray override variables before anything else.  This runs
# immediately and unconditionally — before platform selection, download,
# extraction, or execution — so no override can ever be silently honored.
for _var in "${_TEST_OVERRIDE_VARS[@]}"; do
    # Using indirect expansion to check if the variable is set and non-empty.
    eval "_val=\"\${${_var}:-}\""
    if [ -n "$_val" ]; then
        if ! _harness_active; then
            echo "FAIL: ${_var} is set but ACTIONLINT_TEST_HARNESS is not exactly '1'." >&2
            echo "  Test overrides require ACTIONLINT_TEST_HARNESS=1." >&2
            echo "  Unset ${_var} or set ACTIONLINT_TEST_HARNESS=1 explicitly." >&2
            exit 1
        fi
    fi
done

# _test_overrides_allowed() is only reached after the stray-variable gate
# above has passed.  It confirms the harness is active.
_test_overrides_allowed() {
    _harness_active
}

# -----------------------------------------------------------------------
# Platform detection
# -----------------------------------------------------------------------
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

# -----------------------------------------------------------------------
# Normalize common uname aliases to canonical actionlint identifiers
# -----------------------------------------------------------------------
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

# -----------------------------------------------------------------------
# Platform manifest: sets ASSET_FILENAME and EXPECTED_SHA256 for the given
# normalized "os arch" pair.
#
# SHA-256 values sourced from the official v1.7.12 release checksums file:
#   https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_checksums.txt
# -----------------------------------------------------------------------
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

# -----------------------------------------------------------------------
# Checksum helper (works on Linux with sha256sum and macOS with shasum)
# -----------------------------------------------------------------------
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

# -----------------------------------------------------------------------
# FIX3-B: Exact version parser
#
# Parses actionlint -version output. The real actionlint outputs:
#   1.7.12
#   https://github.com/rhysd/actionlint
#   ...
#
# We extract the first whitespace-stripped line and require it to be
# EXACTLY the expected version string.  No substring matching.
# -----------------------------------------------------------------------
parse_and_verify_version() {
    local candidate_bin="$1"
    local expected="$2"

    local version_output
    # Capture stdout+stderr, but treat command failure as rejection
    if ! version_output="$("$candidate_bin" -version 2>&1)"; then
        echo "FAIL: actionlint -version command failed" >&2
        echo "  output: ${version_output}" >&2
        return 1
    fi

    # Extract the first non-empty line, trimmed of surrounding whitespace
    local first_line
    first_line="$(echo "$version_output" | sed '/^[[:space:]]*$/d' | head -1 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

    if [ "$first_line" != "$expected" ]; then
        echo "FAIL: actionlint version mismatch" >&2
        echo "  expected (exact): ${expected}" >&2
        echo "  parsed version:   ${first_line}" >&2
        echo "  raw output:       ${version_output}" >&2
        return 1
    fi
    return 0
}

# -----------------------------------------------------------------------
# --print-selection: output "asset_filename sha256" for the detected platform
# without downloading. Used by behavioral tests.
# -----------------------------------------------------------------------
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
FINAL_BIN="${INSTALL_DIR}/actionlint"

# --- Verify required utilities ---
CURL_BIN="curl"
if _test_overrides_allowed && [ -n "${ACTIONLINT_TEST_CURL:-}" ]; then
    CURL_BIN="$ACTIONLINT_TEST_CURL"
fi
if ! command -v "$CURL_BIN" >/dev/null 2>&1; then
    echo "FAIL: Required utility '$CURL_BIN' not found on PATH" >&2
    exit 1
fi
if ! command -v tar >/dev/null 2>&1; then
    echo "FAIL: Required utility 'tar' not found on PATH" >&2
    exit 1
fi
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

# --- Determine download URL (test override only with harness) ---
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
ATOMIC_TMP=''

# FIX4-A: Single file-cleanup function that removes the download/extraction
# TMPDIR and any still-active destination staging file. Tolerates unset,
# empty, nonexistent, and partially created paths. Never removes FINAL_BIN
# or any pre-existing trusted binary. Called by every signal handler below.
_cleanup_files() {
    if [ -n "${TMPDIR:-}" ] && [ -d "${TMPDIR:-}" ]; then
        rm -rf -- "$TMPDIR" 2>/dev/null || true
    fi
    if [ -n "${ATOMIC_TMP:-}" ] && [ -e "${ATOMIC_TMP:-}" ]; then
        rm -f -- "$ATOMIC_TMP" 2>/dev/null || true
    fi
}

# Separate signal handlers with explicit exit statuses.
# Each handler disables all traps before calling _cleanup_files, so cleanup
# runs exactly once even if a second signal arrives during cleanup.
_on_exit() {
    local rc=$?
    trap - EXIT INT TERM
    _cleanup_files
    exit "$rc"
}

_on_int() {
    trap - EXIT INT TERM
    _cleanup_files
    exit 130
}

_on_term() {
    trap - EXIT INT TERM
    _cleanup_files
    exit 143
}

trap _on_exit EXIT
trap _on_int INT
trap _on_term TERM

# --- Download ---
echo "[install_actionlint] Downloading from ${DOWNLOAD_URL}..." >&2
TARBALL_PATH="${TMPDIR}/${ASSET_FILENAME}"
if ! "$CURL_BIN" -fsSL -o "$TARBALL_PATH" "$DOWNLOAD_URL"; then
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

# --- Extract candidate to staging (NOT to INSTALL_DIR) ---
if ! tar -xzf "$TARBALL_PATH" -C "$TMPDIR" actionlint; then
    echo "FAIL: Could not extract actionlint binary from tarball" >&2
    exit 1
fi

CANDIDATE_BIN="${TMPDIR}/actionlint"
chmod +x "$CANDIDATE_BIN"

# --- FIX3-B: Validate candidate exact version BEFORE touching INSTALL_DIR ---
echo "[install_actionlint] Verifying actionlint exact version..." >&2
if ! parse_and_verify_version "$CANDIDATE_BIN" "$ACTIONLINT_VERSION"; then
    exit 1
fi
echo "[install_actionlint] Version verified (exact match): ${ACTIONLINT_VERSION}" >&2

# --- FIX4-A: Atomic install with mktemp staging and managed cleanup ---
# Copy candidate to an unpredictable temp file inside the destination
# filesystem (same fs as FINAL_BIN for atomic rename), set executable
# permissions, then rename into the final path.
mkdir -p "$INSTALL_DIR"

ATOMIC_TMP="$(mktemp "${INSTALL_DIR}/.actionlint.tmp.XXXXXX")"
if ! cp "$CANDIDATE_BIN" "$ATOMIC_TMP"; then
    echo "FAIL: Could not stage candidate for atomic install" >&2
    exit 1
fi
if ! chmod +x "$ATOMIC_TMP"; then
    echo "FAIL: Could not set executable permissions on staging file" >&2
    exit 1
fi

if ! mv -f "$ATOMIC_TMP" "$FINAL_BIN"; then
    echo "FAIL: Could not atomically install actionlint" >&2
    exit 1
fi

# Clear staging variable so the EXIT trap cleanup does not remove the
# freshly installed binary.
ATOMIC_TMP=''

echo "[install_actionlint] Installed actionlint to ${FINAL_BIN}" >&2
# Only stdout line: the install directory path
echo "$INSTALL_DIR"
