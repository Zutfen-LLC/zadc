"""Models package for ZADC canonical artifacts."""

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

__all__ = [
    # A1 envelope
    "ArtifactEnvelope",
    "PolicyReference",
    "ProducerIdentity",
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
]
