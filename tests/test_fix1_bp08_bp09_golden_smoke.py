"""FIX1-BP-08: Golden vector and PYTHONHASHSEED determinism.
Also FIX1-BP-09: Package/API smoke test.
"""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    canonical_json_bytes,
    canonical_json_text,
    compute_content_digest,
)


def _make_envelope() -> ArtifactEnvelope:
    return ArtifactEnvelope(
        artifact_type="packet",
        artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
        created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
        producer=ProducerIdentity(actor_type="human", actor_id="zutfen:human:eric"),
        project_id="zutfen:project:zadc",
        slice_id="ZADC-001A",
        slice_instance_id="ZADC-001A1",
        policy=PolicyReference(
            policy_id="zutfen:zadc-policy:standard@0.1.0",
            policy_source_sha="a" * 40,
            policy_digest="sha256:" + "b" * 64,
        ),
        provenance=Provenance(parent_artifact_ids=()),
    )


class TestGoldenVector:
    """FIX1-BP-08: Fixed expected golden vectors."""

    def test_exact_digest_input_bytes(self) -> None:
        """Record exact expected digest-input bytes (no content_digest key)."""
        from zadc.digests import get_digest_input_bytes

        env = _make_envelope()
        raw = get_digest_input_bytes(env)
        expected = (
            b'{"artifact_id":"urn:uuid:00000000-0000-0000-0000-000000000001",'
            b'"artifact_type":"packet","contract_version":"0.1.0",'
            b'"created_at":"2026-07-31T12:00:00Z",'
            b'"policy":{"policy_digest":"sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",'
            b'"policy_id":"zutfen:zadc-policy:standard@0.1.0",'
            b'"policy_source_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},'
            b'"producer":{"actor_id":"zutfen:human:eric","actor_type":"human",'
            b'"model":null,"provider":null,"run_id":null},'
            b'"project_id":"zutfen:project:zadc",'
            b'"provenance":{"parent_artifact_ids":[]},'
            b'"schema":"https://schemas.zutfen.com/zadc/0.1/artifact.schema.json",'
            b'"slice_id":"ZADC-001A","slice_instance_id":"ZADC-001A1"}'
        )
        assert raw == expected

    def test_exact_expected_digest(self) -> None:
        """Fixed expected sha256 digest."""
        env = _make_envelope()
        assert (
            compute_content_digest(env)
            == "sha256:99676878dd6383eb924022e02b2f6e9f20d479e3ae304ad834fda444632e3e60"
        )

    def test_round_trip_idempotent(self) -> None:
        """Canonical output is idempotent."""
        env = _make_envelope()
        once = canonical_json_text(env)
        parsed = json.loads(once)
        twice = canonical_json_text(parsed)
        assert once == twice


class TestHashseedDeterminism:
    """PYTHONHASHSEED determinism."""

    _SUBPROCESS_CODE = r"""
import sys
sys.path.insert(0, "src")
from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    canonical_json_bytes,
    compute_content_digest,
)
from datetime import datetime, timezone
import hashlib

data = {f"key_{i:03d}": {f"sub_{j:03d}": i*j for j in range(20)} for i in range(30)}
result = canonical_json_bytes(data)
print(hashlib.sha256(result).hexdigest())

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

    def _run_subprocess(self, repo_root: str, hashseed: str) -> tuple[str, str]:
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = hashseed
        result = subprocess.run(
            [sys.executable, "-c", self._SUBPROCESS_CODE],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env=env,
        )
        assert result.returncode == 0, f"subprocess failed: {result.stderr}"
        lines = result.stdout.strip().split("\n")
        return lines[0], lines[1]

    @pytest.fixture
    def repo_root(self) -> str:
        return str(Path(__file__).resolve().parent.parent)

    def test_at_least_three_seeds_identical(self, repo_root: str) -> None:
        seeds = ["0", "1", "42"]
        results = [self._run_subprocess(repo_root, s) for s in seeds]
        canonical_hashes = [r[0] for r in results]
        assert len(set(canonical_hashes)) == 1
        digests = [r[1] for r in results]
        assert len(set(digests)) == 1


class TestCanonicalJSONProfile:
    """Canonical JSON profile rules still hold."""

    def test_no_bom(self) -> None:
        result = canonical_json_bytes({"key": "value"})
        assert not result.startswith(b"\xef\xbb\xbf")

    def test_no_trailing_newline(self) -> None:
        result = canonical_json_bytes({"key": "value"})
        assert not result.endswith(b"\n")

    def test_keys_sorted(self) -> None:
        result = canonical_json_text({"zebra": 1, "apple": 2})
        assert result == '{"apple":2,"zebra":1}'

    def test_compact_separators(self) -> None:
        result = canonical_json_text({"a": 1})
        assert result == '{"a":1}'

    def test_floats_rejected(self) -> None:
        from zadc.canonical import CanonicalJSONTypeError

        with pytest.raises(CanonicalJSONTypeError):
            canonical_json_text(3.14)

    def test_unicode_direct(self) -> None:
        result = canonical_json_text("héllo")
        assert result == '"héllo"'

    def test_null_preserved(self) -> None:
        result = canonical_json_text({"key": None})
        assert result == '{"key":null}'
