"""FIX2-BP-08: Digest and canonical vectors remain stable under corrected required fields.

Tests that the golden payload bytes and expected digest remain stable,
the digest payload excludes content_digest, and direct BaseModel
canonicalization, deep immutability, sealing, verification, and
PYTHONHASHSEED determinism remain green.
"""

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
    seal_artifact,
    verify_content_digest,
)
from zadc.digests import get_digest_input_bytes
from zadc.types import CONTRACT_VERSION, SCHEMA_ID


def _make_envelope() -> ArtifactEnvelope:
    return ArtifactEnvelope(
        schema=SCHEMA_ID,
        contract_version=CONTRACT_VERSION,
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


class TestGoldenVectorStable:
    """Refresh exact golden payload bytes and digest — they remain stable."""

    def test_exact_digest_input_bytes(self) -> None:
        """Exact expected digest-input bytes (no content_digest key)."""
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
        """Fixed expected sha256 digest — unchanged from FIX1."""
        env = _make_envelope()
        assert (
            compute_content_digest(env)
            == "sha256:99676878dd6383eb924022e02b2f6e9f20d479e3ae304ad834fda444632e3e60"
        )


class TestDigestExcludesContentDigest:
    """The digest payload still excludes content_digest entirely."""

    def test_content_digest_key_absent(self) -> None:
        env = _make_envelope()
        raw = get_digest_input_bytes(env)
        assert b"content_digest" not in raw

    def test_sealed_envelope_digest_excludes_content_digest(self) -> None:
        env = _make_envelope()
        sealed = seal_artifact(env)
        raw = get_digest_input_bytes(sealed)
        assert b"content_digest" not in raw


class TestCanonicalizationAndImmutability:
    """Direct BaseModel canonicalization, deep immutability, sealing, verification remain green."""

    def test_direct_model_canonicalization(self) -> None:
        env = _make_envelope()
        text = canonical_json_text(env)
        assert isinstance(text, str)
        assert '"schema":' in text
        assert '"contract_version":"0.1.0"' in text

    def test_omitted_vs_explicit_defaults_identical(self) -> None:
        env_explicit = ArtifactEnvelope(
            schema=SCHEMA_ID,
            contract_version=CONTRACT_VERSION,
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000002",
            created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
            producer=ProducerIdentity(
                actor_type="human",
                actor_id="zutfen:human:eric",
                run_id=None,
                model=None,
                provider=None,
            ),
            project_id="zutfen:project:zadc",
            slice_id="ZADC-001A",
            slice_instance_id="ZADC-001A1",
            policy=PolicyReference(
                policy_id="zutfen:zadc-policy:standard@0.1.0",
                policy_source_sha="a" * 40,
                policy_digest="sha256:" + "b" * 64,
            ),
            provenance=Provenance(parent_artifact_ids=(), content_digest=None),
        )
        # Different artifact_id -> different bytes, so check same-id
        env_omitted2 = ArtifactEnvelope(
            schema=SCHEMA_ID,
            contract_version=CONTRACT_VERSION,
            artifact_type="packet",
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000002",
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
        assert canonical_json_bytes(env_omitted2) == canonical_json_bytes(env_explicit)

    def test_parent_artifact_ids_immutable(self) -> None:
        prov = Provenance(parent_artifact_ids=("urn:uuid:00000000-0000-0000-0000-000000000098",))
        with pytest.raises(AttributeError):
            prov.parent_artifact_ids.append("x")  # type: ignore[attr-defined]

    def test_seal_does_not_mutate_input(self) -> None:
        env = _make_envelope()
        sealed = seal_artifact(env)
        assert env.provenance.content_digest is None
        assert sealed.provenance.content_digest is not None

    def test_sealed_verifies(self) -> None:
        env = _make_envelope()
        sealed = seal_artifact(env)
        result = verify_content_digest(sealed)
        assert result == sealed.provenance.content_digest

    def test_envelope_immutable(self) -> None:
        env = _make_envelope()
        from pydantic import ValidationError

        with pytest.raises((ValidationError, TypeError)):
            env.artifact_id = "changed"


class TestHashseedDeterminism:
    """PYTHONHASHSEED determinism."""

    _SUBPROCESS_CODE = """
import sys
sys.path.insert(0, "src")
from zadc import (
    ArtifactEnvelope, PolicyReference, ProducerIdentity, Provenance,
    canonical_json_bytes, compute_content_digest,
)
from zadc.types import SCHEMA_ID, CONTRACT_VERSION
from datetime import datetime, timezone
import hashlib

data = {f"key_{i:03d}": {f"sub_{j:03d}": i*j for j in range(20)} for i in range(30)}
result = canonical_json_bytes(data)
print(hashlib.sha256(result).hexdigest())

env = ArtifactEnvelope(
    schema=SCHEMA_ID, contract_version=CONTRACT_VERSION,
    artifact_type="packet",
    artifact_id="urn:uuid:00000000-0000-0000-0000-000000000050",
    created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc),
    producer={"actor_type": "human", "actor_id": "zutfen:human:test"},
    project_id="zutfen:project:zadc",
    slice_id="HASH-001", slice_instance_id="HASH-001A",
    policy={"policy_id": "zutfen:zadc-policy:standard@0.1.0",
            "policy_source_sha": "a" * 40,
            "policy_digest": "sha256:" + "b" * 64},
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
