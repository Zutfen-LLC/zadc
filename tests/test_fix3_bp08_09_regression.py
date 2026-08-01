"""FIX3-BP-08: Schema reproducibility and integrity.

FIX3-BP-09: A1 regression and package smoke.
"""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    canonical_json_text,
    compute_content_digest,
    seal_artifact,
    verify_content_digest,
)
from zadc.types import CONTRACT_VERSION, SCHEMA_ID

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_schemas import _build_envelope_schema  # noqa: E402

_SCHEMA_PATH = _REPO_ROOT / "schemas" / "0.1" / "artifact-envelope.schema.json"


class TestFix3BP08SchemaIntegrity:
    """FIX3-BP-08: Schema reproducibility and integrity."""

    def test_check_schema_valid(self) -> None:
        schema = cast(dict[str, Any], json.loads(_SCHEMA_PATH.read_text()))
        Draft202012Validator.check_schema(schema)

    def test_byte_identical_regeneration(self) -> None:
        committed = _SCHEMA_PATH.read_text()
        schema = cast(dict[str, Any], _build_envelope_schema())
        generated = json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        assert committed == generated

    def test_no_local_paths(self) -> None:
        schema_str = _SCHEMA_PATH.read_text()
        assert "/home/" not in schema_str
        assert "/tmp/" not in schema_str

    def test_no_random_values(self) -> None:
        import re

        schema_str = _SCHEMA_PATH.read_text()
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:", schema_str)
        assert "uuid-" not in schema_str.lower()

    def test_schema_sha256(self) -> None:
        """Record exact schema SHA-256 for the completion report."""
        content = _SCHEMA_PATH.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        # The digest will change if schema changes; this test documents it.
        assert len(digest) == 64
        # Print for the completion report
        print(f"Schema SHA-256: {digest}")


# ---------------------------------------------------------------------------
# FIX3-BP-09: A1 regression and package smoke
# ---------------------------------------------------------------------------


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


class TestFix3BP09Regression:
    """FIX3-BP-09: All prior A1 regression proofs remain green."""

    def test_golden_digest_unchanged(self) -> None:
        env = _make_envelope()
        assert (
            compute_content_digest(env)
            == "sha256:99676878dd6383eb924022e02b2f6e9f20d479e3ae304ad834fda444632e3e60"
        )

    def test_digest_excludes_content_digest(self) -> None:
        from zadc.digests import get_digest_input_bytes

        env = _make_envelope()
        raw = get_digest_input_bytes(env)
        assert b"content_digest" not in raw

    def test_direct_model_canonicalization(self) -> None:
        env = _make_envelope()
        text = canonical_json_text(env)
        assert isinstance(text, str)
        assert '"schema":' in text

    def test_deep_immutability(self) -> None:
        env = _make_envelope()
        from pydantic import ValidationError

        with pytest.raises((ValidationError, TypeError)):
            env.artifact_id = "changed"

    def test_seal_and_verify(self) -> None:
        env = _make_envelope()
        sealed = seal_artifact(env)
        assert sealed.provenance.content_digest is not None
        result = verify_content_digest(sealed)
        assert result == sealed.provenance.content_digest

    def test_required_constants(self) -> None:
        env = _make_envelope()
        assert env.schema_uri == SCHEMA_ID
        assert env.contract_version == CONTRACT_VERSION

    def test_sealed_envelope_schema_validates(self) -> None:
        """Sealed envelope validates against the committed schema."""
        schema = cast(dict[str, Any], json.loads(_SCHEMA_PATH.read_text()))
        v = Draft202012Validator(schema, format_checker=FormatChecker())
        env = _make_envelope()
        sealed = seal_artifact(env)
        data = cast(dict[str, Any], json.loads(canonical_json_text(sealed)))
        errors = list(v.iter_errors(data))
        assert errors == []

    def test_no_a3_plus_symbols(self) -> None:
        """A2A adds Packet/CompletionReport; A2B1 adds ReviewReport/
        DecisionRecord; A2B2 adds WorkflowBundle/ZadcArtifact; later-slice
        symbols (lifecycle derivation, policy evaluation, provider adapters,
        renderers, Engram/Flowstate integration) remain absent."""
        import zadc

        prohibited = {
            "LifecycleState",
            "PolicyEvaluator",
            "GitAdapter",
            "GitHubAdapter",
            "Renderer",
            "EngramIntegration",
            "FlowstateIntegration",
        }
        for name in prohibited:
            assert not hasattr(zadc, name)
