"""FIX1-BP-04: Direct model canonicalization.

Tests that canonical_json_bytes/text accept Pydantic BaseModel instances
directly and produce output equal to the fixed dump profile.
"""

from datetime import UTC, datetime

import pytest

from zadc import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
    canonical_json_bytes,
    canonical_json_text,
)
from zadc.canonical import CanonicalJSONTypeError


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


class TestDirectModelCanonicalization:
    """canonical_json_bytes/text accept BaseModel instances directly."""

    def test_accepts_artifact_envelope(self) -> None:
        env = _make_envelope()
        text = canonical_json_text(env)
        assert isinstance(text, str)
        # Unsealed envelope includes content_digest:null (exclude_none=False)
        assert '"content_digest":null' in text

    def test_accepts_producer_identity(self) -> None:
        prod = ProducerIdentity(actor_type="human", actor_id="zutfen:human:eric")
        text = canonical_json_text(prod)
        assert isinstance(text, str)

    def test_accepts_provenance(self) -> None:
        prov = Provenance(parent_artifact_ids=())
        text = canonical_json_text(prov)
        assert isinstance(text, str)

    def test_bytes_and_text_consistent(self) -> None:
        env = _make_envelope()
        text = canonical_json_text(env)
        byts = canonical_json_bytes(env)
        assert text.encode("utf-8") == byts

    def test_direct_model_equals_fixed_dump_profile(self) -> None:
        """Direct-model output equals the documented fixed model_dump profile."""
        env = _make_envelope()
        dumped = env.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=False,
            exclude_defaults=False,
            exclude_unset=False,
        )
        # canonical_json_text on the model should equal canonical_json_text on the dump
        direct = canonical_json_text(env)
        from_dump = canonical_json_text(dumped)
        assert direct == from_dump

    def test_omitted_vs_explicit_defaults_identical(self) -> None:
        """Omitted defaults vs explicitly supplied defaults/nulls produce identical bytes."""
        env_omitted = ArtifactEnvelope(
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
        env_explicit = ArtifactEnvelope(
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
        assert canonical_json_bytes(env_omitted) == canonical_json_bytes(env_explicit)

    def test_aliases_present_python_names_absent(self) -> None:
        """The 'schema' alias is present and the python field name 'schema_uri' is absent."""
        env = _make_envelope()
        text = canonical_json_text(env)
        assert '"schema":' in text
        assert "schema_uri" not in text

    def test_arbitrary_non_pydantic_objects_rejected(self) -> None:
        class Custom:
            pass

        with pytest.raises(CanonicalJSONTypeError):
            canonical_json_text(Custom())

    def test_no_default_str_fallback(self) -> None:
        """Arbitrary objects with __str__ are not accepted via default=str."""

        class HasRepr:
            def __repr__(self) -> str:
                return "HasRepr()"

        with pytest.raises(CanonicalJSONTypeError):
            canonical_json_text(HasRepr())
