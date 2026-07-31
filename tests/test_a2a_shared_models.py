"""A2A-03: shared supporting models (ArtifactReference, EvidenceReference,
ExactSubject, VerificationEnvironment, ObservationSource, ExecutorClaim)."""

import pytest
from pydantic import ValidationError

from zadc.models.shared import (
    ArtifactReference,
    EvidenceReference,
    ExactSubject,
    ExecutorClaim,
    ObservationSource,
    VerificationEnvironment,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
DIGEST = "sha256:" + "d" * 64


class TestArtifactReference:
    def test_valid(self) -> None:
        ref = ArtifactReference(
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001", content_digest=DIGEST
        )
        assert ref.content_digest == DIGEST

    def test_frozen(self) -> None:
        ref = ArtifactReference(
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001", content_digest=DIGEST
        )
        with pytest.raises(ValidationError):
            ref.content_digest = "sha256:" + "0" * 64

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactReference(
                artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
                content_digest=DIGEST,
                extra="nope",  # type: ignore[call-arg]
            )

    def test_rejects_missing_fields(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactReference(artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001")  # type: ignore[call-arg]


class TestEvidenceReference:
    def test_valid(self) -> None:
        ref = EvidenceReference(
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
            media_type="text/plain",
            digest=DIGEST,
            location="https://ci.example.com/log.txt",
        )
        assert ref.media_type == "text/plain"

    def test_rejects_bad_media_type(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceReference(
                artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
                media_type="not-a-media-type",
                digest=DIGEST,
                location="https://ci.example.com/log.txt",
            )

    def test_rejects_bad_digest(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceReference(
                artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
                media_type="text/plain",
                digest="not-a-digest",
                location="https://ci.example.com/log.txt",
            )


class TestExactSubject:
    def test_commit_subject_no_extra_shas_required(self) -> None:
        subject = ExactSubject(
            repository_id="github:Zutfen-LLC/zadc", subject_kind="commit", subject_sha=SHA_A
        )
        assert subject.base_sha is None

    def test_pr_head_requires_head_sha_equal_subject_sha(self) -> None:
        subject = ExactSubject(
            repository_id="github:Zutfen-LLC/zadc",
            subject_kind="pr_head",
            subject_sha=SHA_A,
            head_sha=SHA_A,
        )
        assert subject.head_sha == SHA_A

    def test_pr_head_rejects_mismatched_head_sha(self) -> None:
        with pytest.raises(ValidationError, match="pr_head"):
            ExactSubject(
                repository_id="github:Zutfen-LLC/zadc",
                subject_kind="pr_head",
                subject_sha=SHA_A,
                head_sha=SHA_B,
            )

    def test_pr_head_rejects_missing_head_sha(self) -> None:
        with pytest.raises(ValidationError, match="pr_head"):
            ExactSubject(
                repository_id="github:Zutfen-LLC/zadc",
                subject_kind="pr_head",
                subject_sha=SHA_A,
            )

    def test_synthetic_merge_requires_all_three_shas(self) -> None:
        subject = ExactSubject(
            repository_id="github:Zutfen-LLC/zadc",
            subject_kind="synthetic_merge",
            subject_sha=SHA_C,
            base_sha=SHA_A,
            head_sha=SHA_B,
            synthetic_merge_sha=SHA_C,
        )
        assert subject.synthetic_merge_sha == SHA_C

    def test_synthetic_merge_rejects_missing_base_sha(self) -> None:
        with pytest.raises(ValidationError, match="synthetic_merge"):
            ExactSubject(
                repository_id="github:Zutfen-LLC/zadc",
                subject_kind="synthetic_merge",
                subject_sha=SHA_C,
                head_sha=SHA_B,
                synthetic_merge_sha=SHA_C,
            )

    def test_synthetic_merge_rejects_missing_head_sha(self) -> None:
        with pytest.raises(ValidationError, match="synthetic_merge"):
            ExactSubject(
                repository_id="github:Zutfen-LLC/zadc",
                subject_kind="synthetic_merge",
                subject_sha=SHA_C,
                base_sha=SHA_A,
                synthetic_merge_sha=SHA_C,
            )

    def test_synthetic_merge_rejects_missing_synthetic_merge_sha(self) -> None:
        with pytest.raises(ValidationError, match="synthetic_merge"):
            ExactSubject(
                repository_id="github:Zutfen-LLC/zadc",
                subject_kind="synthetic_merge",
                subject_sha=SHA_C,
                base_sha=SHA_A,
                head_sha=SHA_B,
            )

    def test_synthetic_merge_rejects_subject_sha_mismatch(self) -> None:
        with pytest.raises(ValidationError, match="synthetic_merge"):
            ExactSubject(
                repository_id="github:Zutfen-LLC/zadc",
                subject_kind="synthetic_merge",
                subject_sha=SHA_A,
                base_sha=SHA_A,
                head_sha=SHA_B,
                synthetic_merge_sha=SHA_C,
            )

    def test_merge_commit_subject_unconstrained(self) -> None:
        subject = ExactSubject(
            repository_id="github:Zutfen-LLC/zadc",
            subject_kind="merge_commit",
            subject_sha=SHA_C,
        )
        assert subject.subject_kind == "merge_commit"


class TestVerificationEnvironment:
    def test_valid_with_lists_normalizes_to_tuples(self) -> None:
        env = VerificationEnvironment(
            runner_identity="github:actions-runner:ubuntu-latest",
            os="ubuntu-24.04",
            architecture="x86_64",
            toolchain=["python-3.13", "uv-0.8.13"],  # type: ignore[arg-type]
            container_digests=[DIGEST],  # type: ignore[arg-type]
        )
        assert env.toolchain == ("python-3.13", "uv-0.8.13")
        assert isinstance(env.toolchain, tuple)
        assert env.container_digests == (DIGEST,)

    def test_accepts_empty_collections(self) -> None:
        env = VerificationEnvironment(
            runner_identity="github:actions-runner:ubuntu-latest",
            os="ubuntu-24.04",
            architecture="x86_64",
            toolchain=(),
            container_digests=(),
        )
        assert env.toolchain == ()


class TestObservationSource:
    def test_valid_minimal(self) -> None:
        source = ObservationSource(source_type="github", source_id="github:Zutfen-LLC/zadc")
        assert source.source_event_id is None

    def test_valid_with_event_id(self) -> None:
        source = ObservationSource(
            source_type="ci", source_id="github:Zutfen-LLC/zadc", source_event_id="run-123"
        )
        assert source.source_event_id == "run-123"


class TestExecutorClaim:
    def test_default_epistemic_status_is_agent_reported(self) -> None:
        claim = ExecutorClaim(statement="tests passed", evidence_refs=())
        assert claim.epistemic_status == "AGENT_REPORTED"

    def test_explicit_epistemic_status(self) -> None:
        claim = ExecutorClaim(
            statement="tests passed", epistemic_status="LOCALLY_OBSERVED", evidence_refs=()
        )
        assert claim.epistemic_status == "LOCALLY_OBSERVED"

    def test_evidence_refs_normalizes_list_to_tuple(self) -> None:
        ref = EvidenceReference(
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
            media_type="text/plain",
            digest=DIGEST,
            location="https://ci.example.com/log.txt",
        )
        claim = ExecutorClaim(statement="tests passed", evidence_refs=[ref])  # type: ignore[arg-type]
        assert claim.evidence_refs == (ref,)
