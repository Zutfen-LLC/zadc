"""The Packet artifact: authoritative, human-approved work authorization.

Implements architecture sections 8.5 and 11.1. The packet is the
authorization boundary: an execution agent MUST NOT begin authorized work
without a valid packet, and a substantive change to an authorized packet
MUST create a new packet revision with a new artifact ID and an explicit
``supersedes`` relationship rather than mutating the original.

Packet immutability in this slice is structural only — the model is frozen
and content-digest sealed. Binding packet authorization to a trusted human
identity, and cross-artifact packet-digest reconciliation against downstream
completion reports and certification manifests, are deferred to a later
validation slice (not implemented here).
"""

from typing import Annotated, Literal, Optional

from pydantic import BeforeValidator, PositiveInt, model_validator

from zadc.models.common import ArtifactEnvelope, _ZadcModel
from zadc.models.shared import ArtifactReference
from zadc.types import (
    ConstrainedText,
    ExactSubjectPolicy,
    FindingSeverity,
    GitHubName,
    GitSha,
    GlobalId,
    MismatchPolicy,
    StableId,
    Timestamp,
    coerce_tuple,
)


class PacketAuthorization(_ZadcModel):
    """The trusted human authorization binding for a packet (architecture 11.1)."""

    authorized_by: GlobalId
    authorized_at: Timestamp
    expires_at: Optional[Timestamp] = None

    @model_validator(mode="after")
    def _check_expiry(self) -> "PacketAuthorization":
        if self.expires_at is not None and self.expires_at <= self.authorized_at:
            raise ValueError("expires_at must be later than authorized_at")
        return self


class RepositoryTarget(_ZadcModel):
    """The repository identity and optional pull-request target of a packet."""

    repository_id: GlobalId
    provider: Literal["github"]
    owner: GitHubName
    name: GitHubName
    pull_request: Optional[PositiveInt] = None


class WorkStartAuthorization(_ZadcModel):
    """The authorized work-start commit and mismatch policy (architecture 13)."""

    expected_sha: GitSha
    mismatch_policy: MismatchPolicy


class PacketIntent(_ZadcModel):
    """The authorized problem statement and desired outcome."""

    problem_statement: ConstrainedText
    desired_outcome: ConstrainedText


class PacketScope(_ZadcModel):
    """The authorized and prohibited paths and operations for a packet."""

    allowed_paths: Annotated[tuple[ConstrainedText, ...], BeforeValidator(coerce_tuple)]
    prohibited_paths: Annotated[tuple[ConstrainedText, ...], BeforeValidator(coerce_tuple)]
    allowed_operations: Annotated[tuple[ConstrainedText, ...], BeforeValidator(coerce_tuple)]
    prohibited_operations: Annotated[tuple[ConstrainedText, ...], BeforeValidator(coerce_tuple)]


class Requirement(_ZadcModel):
    """One normative requirement with its acceptance criteria."""

    requirement_id: StableId
    statement: ConstrainedText
    acceptance_criteria: Annotated[tuple[ConstrainedText, ...], BeforeValidator(coerce_tuple)]


class DependencyPin(_ZadcModel):
    """A pinned cross-repository dependency (architecture 8.2, goal 7)."""

    repository_id: GlobalId
    sha: GitSha
    cleanliness_required: bool


class VerificationRequirements(_ZadcModel):
    """The mandatory/advisory verification lanes and exact-subject policy."""

    mandatory_lanes: Annotated[tuple[StableId, ...], BeforeValidator(coerce_tuple)]
    advisory_lanes: Annotated[tuple[StableId, ...], BeforeValidator(coerce_tuple)]
    exact_subject_policy: ExactSubjectPolicy
    synthetic_merge_required: bool

    @model_validator(mode="after")
    def _check_lane_uniqueness(self) -> "VerificationRequirements":
        if len(self.mandatory_lanes) != len(set(self.mandatory_lanes)):
            raise ValueError("mandatory_lanes must not contain duplicate lane IDs")
        if len(self.advisory_lanes) != len(set(self.advisory_lanes)):
            raise ValueError("advisory_lanes must not contain duplicate lane IDs")
        overlap = set(self.mandatory_lanes) & set(self.advisory_lanes)
        if overlap:
            raise ValueError(
                f"mandatory_lanes and advisory_lanes must not overlap: {sorted(overlap)}"
            )
        return self


class PacketReview(_ZadcModel):
    """The packet's independent-review requirement and blocking threshold."""

    independent_review_required: bool
    minimum_severity_blocking: FindingSeverity


class Packet(ArtifactEnvelope):
    """The authoritative, human-approved work contract (architecture 11.1)."""

    artifact_type: Literal["packet"]

    authorization: PacketAuthorization
    repository: RepositoryTarget
    work_start: WorkStartAuthorization
    intent: PacketIntent
    scope: PacketScope
    requirements: Annotated[tuple[Requirement, ...], BeforeValidator(coerce_tuple)]
    dependency_pins: Annotated[tuple[DependencyPin, ...], BeforeValidator(coerce_tuple)]
    verification: VerificationRequirements
    review: PacketReview
    stop_conditions: Annotated[tuple[ConstrainedText, ...], BeforeValidator(coerce_tuple)]
    deliverables: Annotated[tuple[ConstrainedText, ...], BeforeValidator(coerce_tuple)]
    completion_report_requirements: Annotated[
        tuple[ConstrainedText, ...], BeforeValidator(coerce_tuple)
    ]
    supersedes: Optional[ArtifactReference] = None

    @model_validator(mode="after")
    def _check_packet_invariants(self) -> "Packet":
        ids = [r.requirement_id for r in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("requirement_id values must be unique across the packet")
        if self.supersedes is not None and self.supersedes.artifact_id == self.artifact_id:
            raise ValueError("supersedes must not equal the packet's own artifact_id")
        return self


__all__ = [
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
]
