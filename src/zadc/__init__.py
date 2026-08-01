"""ZADC — Zutfen Agentic Development Contract.

This package provides the canonical artifact substrate: common envelope
models, constrained identifiers/timestamps, deterministic canonical JSON,
SHA-256 sealing/verification, and a reproducible JSON Schema. It also
provides the first concrete A2A artifact models: Packet, CompletionReport,
CertificationManifest, EvidenceArtifact, and Observation.

Public API:
    Types:
        ActorType       — Literal union of valid actor types.
        ArtifactType    — Literal union of valid artifact types.
        GlobalId        — URI-shaped global identifier (annotated str).
        SliceId         — Human-friendly slice identifier (annotated str).
        Sha256Digest    — Annotated str validated as sha256:<64hex>.
        GitSha          — Annotated str validated as 40 lowercase hex.
        Timestamp       — Reusable ZADC Timestamp v0.1 field type.
        ConstrainedText — Reusable bounded prose text type.
        StableId        — Reusable stable identifier type.
        MediaType       — Reusable MIME media type.
        GitHubName      — Reusable GitHub owner/repo name segment.
        RefName         — Reusable Git ref/branch name.
        EpistemicStatus, MismatchPolicy, ExactSubjectPolicy, FindingSeverity,
        ExecutorRecommendation, SubjectKind, LaneClassification,
        LaneConclusion, CertificationResult, EvidenceAvailability,
        ObservationSourceType — shared contract enums (Literal aliases).

    A1 envelope models:
        ArtifactEnvelope  — The common envelope shared by all artifacts.
        ProducerIdentity  — Identity of the producing actor.
        PolicyReference   — Reference to governing policy.
        Provenance        — Parent artifact IDs and content digest.

    A2A concrete artifact models:
        Packet                 — Authoritative work authorization.
        CompletionReport       — Execution agent's completion claim.
        CertificationManifest  — Trusted verification results.
        EvidenceArtifact       — External evidence metadata and binding.
        Observation            — Timestamped statement from a named source.
        Plus their nested supporting models — see ``zadc.models``.

    Canonical JSON:
        canonical_json_bytes(value) -> bytes
        canonical_json_text(value)  -> str

    Digests:
        compute_content_digest(envelope) -> str
        seal_artifact(envelope)          -> type(envelope)
        verify_content_digest(envelope)  -> str

    Errors:
        DigestMissingError  — Envelope has not been sealed.
        DigestMismatchError — Stored digest does not match recomputed digest.
"""

from importlib.metadata import PackageNotFoundError, version

from zadc.canonical import CanonicalJSONTypeError, canonical_json_bytes, canonical_json_text
from zadc.digests import compute_content_digest, seal_artifact, verify_content_digest
from zadc.errors import DigestError, DigestMismatchError, DigestMissingError
from zadc.models.certification_manifest import CertificationManifest, LaneResult
from zadc.models.common import (
    ArtifactEnvelope,
    PolicyReference,
    ProducerIdentity,
    Provenance,
)
from zadc.models.completion_report import (
    Changes,
    CompletionReport,
    DependencyPinResolution,
    Reconciliation,
    ReconciliationCommit,
    RepositoryState,
    VerificationClaims,
    WorkStartObservation,
)
from zadc.models.evidence_artifact import EvidenceArtifact
from zadc.models.observation import Observation
from zadc.models.packet import (
    DependencyPin,
    Packet,
    PacketAuthorization,
    PacketIntent,
    PacketReview,
    PacketScope,
    RepositoryTarget,
    Requirement,
    VerificationRequirements,
    WorkStartAuthorization,
)
from zadc.models.shared import (
    ArtifactReference,
    EvidenceReference,
    ExactSubject,
    ExecutorClaim,
    ObservationSource,
    VerificationEnvironment,
)
from zadc.types import (
    CONTRACT_VERSION,
    SCHEMA_ID,
    ActorType,
    ArtifactType,
    CertificationResult,
    ConstrainedText,
    EpistemicStatus,
    EvidenceAvailability,
    ExactSubjectPolicy,
    ExecutorRecommendation,
    FindingSeverity,
    GitHubName,
    GitSha,
    GlobalId,
    LaneClassification,
    LaneConclusion,
    MediaType,
    MismatchPolicy,
    ObservationSourceType,
    RefName,
    Sha256Digest,
    SliceId,
    StableId,
    SubjectKind,
    Timestamp,
)


def get_version() -> str:
    """Return the installed package version via importlib.metadata."""
    try:
        return version("zutfen-zadc")
    except PackageNotFoundError:  # pragma: no cover
        return "0.0.0+unknown"


__all__ = [
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
]
