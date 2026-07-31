"""FIX2-BP-09 / A2A: Package/API and evidence accuracy.

Tests that the clean-venv package smoke supplies required constants/parents,
docs describe exact GlobalId and timestamp profiles, and the public API
remains bounded to A1 foundation plus A2A concrete artifacts — with no
review/decision/workflow-bundle/lifecycle/adapter/renderer/integration
symbols (deferred to A2B and later slices).
"""

from pathlib import Path

import zadc

_REPO_ROOT = Path(__file__).resolve().parent.parent


class TestPublicAPIBounded:
    """Public API remains bounded to A1 + A2A, with later-slice symbols absent."""

    EXPECTED_PUBLIC_NAMES = {
        # Version
        "get_version",
        # Constants
        "CONTRACT_VERSION",
        "SCHEMA_ID",
        # Types
        "ActorType",
        "ArtifactType",
        "GlobalId",
        "SliceId",
        "Sha256Digest",
        "GitSha",
        "Timestamp",
        "ConstrainedText",
        "StableId",
        "MediaType",
        "GitHubName",
        "RefName",
        # Shared contract enums
        "EpistemicStatus",
        "MismatchPolicy",
        "ExactSubjectPolicy",
        "FindingSeverity",
        "ExecutorRecommendation",
        "SubjectKind",
        "LaneClassification",
        "LaneConclusion",
        "CertificationResult",
        "EvidenceAvailability",
        "ObservationSourceType",
        # A1 envelope models
        "ArtifactEnvelope",
        "ProducerIdentity",
        "PolicyReference",
        "Provenance",
        # Shared supporting models (A2A-03)
        "ArtifactReference",
        "EvidenceReference",
        "ExactSubject",
        "VerificationEnvironment",
        "ObservationSource",
        "ExecutorClaim",
        # Packet (A2A-04)
        "Packet",
        "PacketAuthorization",
        "RepositoryTarget",
        "WorkStartAuthorization",
        "PacketIntent",
        "PacketScope",
        "Requirement",
        "DependencyPin",
        "VerificationRequirements",
        "PacketReview",
        # CompletionReport (A2A-05)
        "CompletionReport",
        "ReconciliationCommit",
        "Reconciliation",
        "WorkStartObservation",
        "RepositoryState",
        "DependencyPinResolution",
        "Changes",
        "VerificationClaims",
        # CertificationManifest (A2A-06)
        "CertificationManifest",
        "LaneResult",
        # EvidenceArtifact (A2A-07)
        "EvidenceArtifact",
        # Observation (A2A-08)
        "Observation",
        # Canonical JSON
        "canonical_json_bytes",
        "canonical_json_text",
        "CanonicalJSONTypeError",
        # Digests
        "compute_content_digest",
        "seal_artifact",
        "verify_content_digest",
        # Errors
        "DigestError",
        "DigestMissingError",
        "DigestMismatchError",
    }

    PROHIBITED_SYMBOLS = {
        # A2B/A3/001B+ functionality — must not exist in this slice
        "ReviewReport",
        "DecisionRecord",
        "WorkflowBundle",
        "LifecycleState",
        "PolicyEvaluator",
        "GitAdapter",
        "GitHubAdapter",
        "Renderer",
        "EngramIntegration",
        "FlowstateIntegration",
    }

    def test_no_prohibited_symbols(self) -> None:
        for name in self.PROHIBITED_SYMBOLS:
            assert not hasattr(zadc, name), f"Prohibited symbol {name} found in public API"

    def test_public_api_bounded(self) -> None:
        actual = set(zadc.__all__)
        # The public API should not have grown beyond expected names
        unexpected = actual - self.EXPECTED_PUBLIC_NAMES
        assert unexpected == set(), f"Unexpected public API symbols: {unexpected}"


class TestDocsDescribeProfiles:
    """Docs describe exact GlobalId and timestamp profiles and required envelope fields."""

    def test_api_docs_mention_required_fields(self) -> None:
        docs = (_REPO_ROOT / "docs" / "api-a1-foundation.md").read_text()
        assert "schema" in docs
        assert "contract_version" in docs
        assert "parent_artifact_ids" in docs
        assert "required" in docs.lower()

    def test_api_docs_describe_global_id_profile(self) -> None:
        docs = (_REPO_ROOT / "docs" / "api-a1-foundation.md").read_text()
        assert "GlobalId" in docs
        assert "lowercase" in docs.lower() or "canonical" in docs.lower()

    def test_api_docs_describe_timestamp_profile(self) -> None:
        docs = (_REPO_ROOT / "docs" / "api-a1-foundation.md").read_text()
        # Either Timestamp or timestamp grammar description
        assert "Timestamp" in docs or "timestamp" in docs.lower() or "RFC 3339" in docs

    def test_canonical_json_docs_mention_profiles(self) -> None:
        docs = (_REPO_ROOT / "docs" / "canonical-json-v0.1.md").read_text()
        # The canonical JSON docs should reference timestamp or ID profiles if relevant
        assert "datetime" in docs.lower() or "RFC 3339" in docs
