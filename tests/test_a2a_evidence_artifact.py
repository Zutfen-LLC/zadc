"""A2A-07: the EvidenceArtifact artifact."""

import pytest
from pydantic import ValidationError

from tests.a2a_factories import DIGEST_C, SHA_B, build_evidence_artifact
from zadc.models.shared import ExactSubject


class TestEvidenceArtifactConstruction:
    def test_valid(self) -> None:
        artifact = build_evidence_artifact()
        assert artifact.artifact_type == "evidence_artifact"
        assert artifact.availability == "available"

    def test_rejects_wrong_artifact_type(self) -> None:
        with pytest.raises(ValidationError):
            build_evidence_artifact(artifact_type="observation")

    def test_rejects_extra_top_level_field(self) -> None:
        with pytest.raises(ValidationError):
            build_evidence_artifact(unexpected="nope")

    def test_size_bytes_optional(self) -> None:
        artifact = build_evidence_artifact(size_bytes=None)
        assert artifact.size_bytes is None

    def test_size_bytes_zero_is_valid(self) -> None:
        artifact = build_evidence_artifact(size_bytes=0)
        assert artifact.size_bytes == 0

    def test_rejects_negative_size_bytes(self) -> None:
        with pytest.raises(ValidationError):
            build_evidence_artifact(size_bytes=-1)

    def test_unavailable_evidence(self) -> None:
        artifact = build_evidence_artifact(availability="unavailable")
        assert artifact.availability == "unavailable"

    def test_digest_distinct_field_from_provenance_content_digest(self) -> None:
        artifact = build_evidence_artifact()
        assert artifact.digest != artifact.provenance.content_digest
        assert artifact.provenance.content_digest is None
        from zadc.digests import seal_artifact

        sealed = seal_artifact(artifact)
        # The payload digest and the envelope's own content digest are
        # independently addressable fields, sealed to different content.
        assert sealed.digest == DIGEST_C
        assert sealed.provenance.content_digest is not None
        assert sealed.digest != sealed.provenance.content_digest

    def test_subject_uses_shared_exact_subject_model(self) -> None:
        artifact = build_evidence_artifact(
            subject=ExactSubject(
                repository_id="github:Zutfen-LLC/zadc",
                subject_kind="pr_head",
                subject_sha=SHA_B,
                head_sha=SHA_B,
            )
        )
        assert artifact.subject.subject_kind == "pr_head"
