"""A1-BP-005: At least three PYTHONHASHSEED subprocesses produce identical bytes/digest."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC

import pytest

from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    canonical_json_bytes,
    compute_content_digest,
)

# The subprocess code that computes canonical bytes and digest for a
# hash-sensitive data structure.
_SUBLABEL_CODE = r"""
import sys
sys.path.insert(0, "src")
from zadc import ArtifactEnvelope, canonical_json_bytes, compute_content_digest
from datetime import datetime, timezone
import hashlib

# Complex dict with many keys (insertion-order varied by caller)
data = {f"key_{i:03d}": {f"sub_{j:03d}": i*j for j in range(20)} for i in range(30)}
result = canonical_json_bytes(data)
print(hashlib.sha256(result).hexdigest())

# Envelope digest
env = ArtifactEnvelope(
    artifact_type="packet",
    artifact_id="urn:uuid:00000000-0000-0000-0000-000000000050",
    created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc),
    producer={"actor_type": "human", "actor_id": "zutfen:human:test"},
    project_id="zutfen:project:zadc",
    slice_id="HASH-001",
    slice_instance_id="HASH-001A",
    policy={
        "policy_id": "zutfen:zadc-policy:standard@0.1.0",
        "policy_source_sha": "a" * 40,
        "policy_digest": "sha256:" + "b" * 64,
    },
    provenance={"parent_artifact_ids": []},
)
print(compute_content_digest(env))
"""


def _run_subprocess(repo_root: str, hashseed: str) -> tuple[str, str]:
    """Run the subprocess with a specific PYTHONHASHSEED.

    Returns (canonical_hash, envelope_digest).
    """
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hashseed
    result = subprocess.run(
        [sys.executable, "-c", _SUBLABEL_CODE],
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=env,
    )
    assert result.returncode == 0, f"subprocess failed: {result.stderr}"
    lines = result.stdout.strip().split("\n")
    return lines[0], lines[1]


@pytest.fixture
def repo_root() -> str:
    """Get the repository root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestHashSeedIndependence:
    """At least 3 PYTHONHASHSEED values produce identical bytes and digests."""

    def test_canonical_bytes_identical_across_hashes(self, repo_root: str) -> None:
        """Canonical bytes hash must be identical regardless of PYTHONHASHSEED."""
        results = [_run_subprocess(repo_root, h) for h in ["0", "1", "42", "12345", "999999"]]
        # All canonical hashes must match
        canonical_hashes = [r[0] for r in results]
        assert len(set(canonical_hashes)) == 1, (
            f"canonical bytes differ across seeds: {canonical_hashes}"
        )

    def test_at_least_three_identical(self, repo_root: str) -> None:
        """At least 3 PYTHONHASHSEED subprocesses produce identical bytes/digest."""
        seeds = ["0", "1", "42"]
        results = [_run_subprocess(repo_root, s) for s in seeds]

        # All canonical hashes must be the same
        canonical_hashes = [r[0] for r in results]
        assert len(set(canonical_hashes)) == 1, (
            f"canonical bytes differ across seeds: {canonical_hashes}"
        )

        # All envelope digests must be the same
        digests = [r[1] for r in results]
        assert len(set(digests)) == 1, f"digests differ across seeds: {digests}"

    def test_direct_canonical_call_deterministic(self) -> None:
        """Direct calls in the same process produce identical results."""
        data = {f"key_{i:03d}": {f"sub_{j:03d}": i * j for j in range(10)} for i in range(20)}
        b1 = canonical_json_bytes(data)
        b2 = canonical_json_bytes(data)
        assert b1 == b2

    def test_digest_deterministic_same_process(self) -> None:
        """Digest computation is deterministic in the same process."""
        from datetime import datetime

        env = ArtifactEnvelope(
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000051",
            created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
            producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:test"),
            project_id="zutfen:project:zadc",
            slice_id="HASH-002",
            slice_instance_id="HASH-002A",
            policy=PolicyReference(
                policy_id="zutfen:zadc-policy:standard@0.1.0",
                policy_source_sha="a" * 40,
                policy_digest="sha256:" + "b" * 64,
            ),
            provenance=Provenance(parent_artifact_ids=[]),
        )
        d1 = compute_content_digest(env)
        d2 = compute_content_digest(env)
        assert d1 == d2
