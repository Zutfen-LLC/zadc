"""The ReviewReport artifact: a reviewer's structured judgment of a subject.

Implements architecture sections 8-14 (A2B1). A review report records what
a reviewer examined and concluded — it is a judgment artifact, not an
authorization artifact. This model does not authenticate reviewer identity,
prove reviewer independence, compute finding-closure or blocking-threshold
policy, or derive merge eligibility. Those remain deferred to later
validation slices (see ``docs/api-a2b1-review-decision-artifacts.md``).

The reviewer's recommendation (``reviewer_recommendation``) is judgment
only. It MUST NOT be interpreted as a merge authorization — only a
:class:`~zadc.models.decision_record.DecisionRecord` with an authenticated
human ``decided_by`` identity records an authoritative decision, and even
that requires trusted binding and live-state reconciliation deferred to a
later slice.
"""

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PositiveInt, model_validator

from zadc.models.common import ArtifactEnvelope, _ZadcModel
from zadc.models.shared import ArtifactReference, EvidenceReference
from zadc.types import (
    ConstrainedText,
    FindingSeverity,
    FindingStatus,
    GitSha,
    GlobalId,
    ReviewerRecommendation,
    Sha256Digest,
    StableId,
    coerce_tuple,
)


def _validate_line_range(start_line: Optional[int], end_line: Optional[int]) -> None:
    """Shared runtime check for an optional file line range.

    ``end_line`` must not be present without ``start_line``, and when both
    are present ``end_line`` must not precede ``start_line``. Reused by
    :class:`ReviewedFile` and :class:`FileFindingLocation` — neither
    inspects the repository or verifies the referenced lines actually
    exist.
    """
    if end_line is not None and start_line is None:
        raise ValueError("end_line must not be present without start_line")
    if start_line is not None and end_line is not None and end_line < start_line:
        raise ValueError("end_line must not precede start_line")


class ReviewerIdentity(_ZadcModel):
    """Identity of the reviewer that produced a :class:`ReviewReport`.

    Distinct from :class:`~zadc.models.common.ProducerIdentity` in that
    ``actor_type`` is narrowed to ``human`` or ``agent`` — a reviewer is
    never a ``ci``, ``validator``, or ``service`` actor. This model records
    the reviewer's claimed identity; it does not authenticate it.
    """

    actor_type: Literal["human", "agent"]
    actor_id: GlobalId
    run_id: Optional[GlobalId] = None
    model: Optional[ConstrainedText] = None
    provider: Optional[ConstrainedText] = None


class ReviewIndependence(_ZadcModel):
    """The reviewer's independence claim relative to the executing actor.

    Records that ``executor_actor_id`` was the executing actor and whether
    independence was ``satisfied``. This is an internal-consistency check
    only (see :class:`ReviewReport`) — it does not prove trusted reviewer
    independence.
    """

    executor_actor_id: GlobalId
    satisfied: bool


class ReviewSubject(_ZadcModel):
    """The exact subject a :class:`ReviewReport` claims to have examined.

    This model records the claimed subject identity only; it does not
    inspect Git, retrieve evidence, or prove that the listed inputs were
    actually reviewed.
    """

    repository_id: GlobalId
    review_subject_sha: GitSha
    packet_digest: Sha256Digest
    certification_manifest_ids: Annotated[tuple[GlobalId, ...], BeforeValidator(coerce_tuple)]

    @model_validator(mode="after")
    def _check_unique_manifest_ids(self) -> "ReviewSubject":
        ids = self.certification_manifest_ids
        if len(ids) != len(set(ids)):
            raise ValueError("certification_manifest_ids must not contain duplicate values")
        return self


class ReviewedFile(_ZadcModel):
    """One file (or file range) claimed as reviewed input."""

    path: ConstrainedText
    start_line: Optional[PositiveInt] = None
    end_line: Optional[PositiveInt] = None

    @model_validator(mode="after")
    def _check_line_range(self) -> "ReviewedFile":
        _validate_line_range(self.start_line, self.end_line)
        return self


class ReviewInputs(_ZadcModel):
    """The diffs, files, and evidence artifacts a review claims to cover."""

    diffs: Annotated[tuple[EvidenceReference, ...], BeforeValidator(coerce_tuple)]
    files: Annotated[tuple[ReviewedFile, ...], BeforeValidator(coerce_tuple)]
    evidence_artifacts: Annotated[tuple[ArtifactReference, ...], BeforeValidator(coerce_tuple)]


class FileFindingLocation(_ZadcModel):
    """A finding location anchored to a file (and optional line range).

    Rejects fields belonging only to another location variant
    (``artifact_id``, ``description``) via strict ``extra="forbid"``. Does
    not verify that the referenced file or line range exists.
    """

    location_type: Literal["file"]
    path: ConstrainedText
    start_line: Optional[PositiveInt] = None
    end_line: Optional[PositiveInt] = None

    @model_validator(mode="after")
    def _check_line_range(self) -> "FileFindingLocation":
        _validate_line_range(self.start_line, self.end_line)
        return self


class ArtifactFindingLocation(_ZadcModel):
    """A finding location anchored to another ZADC artifact by ID.

    Does not perform repository lookup or cross-artifact reference
    resolution — ``artifact_id`` is recorded as claimed only.
    """

    location_type: Literal["artifact"]
    artifact_id: GlobalId


class GeneralFindingLocation(_ZadcModel):
    """A finding location with no file or artifact anchor — free-text only."""

    location_type: Literal["general"]
    description: ConstrainedText


#: The typed, discriminated finding-location union (architecture A2B1).
#: Each variant is strict (``extra="forbid"``), so a location payload
#: carrying a field from another variant (e.g. ``artifact_id`` alongside
#: ``location_type: "file"``) is rejected both at runtime and by the
#: generated JSON Schema's discriminated ``oneOf``.
FindingLocation = Annotated[
    Union[FileFindingLocation, ArtifactFindingLocation, GeneralFindingLocation],
    Field(discriminator="location_type"),
]


def _finding_json_schema_extra(schema: dict[str, Any], model: type[BaseModel]) -> None:
    """Model-owned hook surfacing the resolution-reference presence gates.

    JSON Schema can express "when status is resolved (or accepted_risk),
    resolution_refs has at least one item" via two independent ``if``/
    ``then`` blocks — one per status value, so each condition is
    independently enforced by the generated schema rather than merged into
    a single combined check. It cannot express that a referenced
    resolution actually resolves or closes the finding; that remains
    runtime-only and out of scope entirely (see
    :class:`~zadc.models.review_report.Finding`).
    """
    schema["allOf"] = [
        {
            "if": {
                "properties": {"status": {"const": "resolved"}},
                "required": ["status"],
            },
            "then": {"properties": {"resolution_refs": {"minItems": 1}}},
        },
        {
            "if": {
                "properties": {"status": {"const": "accepted_risk"}},
                "required": ["status"],
            },
            "then": {"properties": {"resolution_refs": {"minItems": 1}}},
        },
    ]


class Finding(_ZadcModel):
    """One review finding with a typed location and lifecycle status.

    Does not verify that a resolution reference resolves or actually
    closes the finding — ``resolution_refs`` records claimed resolution
    evidence only.
    """

    model_config = ConfigDict(json_schema_extra=_finding_json_schema_extra)

    finding_id: StableId
    severity: FindingSeverity
    status: FindingStatus
    location: FindingLocation
    statement: ConstrainedText
    rationale: ConstrainedText
    resolution_refs: Annotated[tuple[ArtifactReference, ...], BeforeValidator(coerce_tuple)]

    @model_validator(mode="after")
    def _check_resolution_refs(self) -> "Finding":
        if self.status == "resolved" and len(self.resolution_refs) == 0:
            raise ValueError("status='resolved' requires at least one resolution reference")
        if self.status == "accepted_risk" and len(self.resolution_refs) == 0:
            raise ValueError("status='accepted_risk' requires at least one resolution reference")
        return self


class ReviewReport(ArtifactEnvelope):
    """A reviewer's structured judgment of an exact subject (architecture A2B1).

    Preserves the distinction between reviewer judgment and authenticated
    human authority: this artifact records what a reviewer examined and
    concluded, and records — but does not authenticate or derive —
    reviewer independence. ``reviewer_recommendation`` is judgment only and
    must never be treated as merge authorization.
    """

    artifact_type: Literal["review_report"]

    packet_id: GlobalId
    review_id: GlobalId
    reviewer: ReviewerIdentity
    independence: ReviewIndependence
    subject: ReviewSubject
    inputs_reviewed: ReviewInputs
    findings: Annotated[tuple[Finding, ...], BeforeValidator(coerce_tuple)]
    limitations: Annotated[tuple[ConstrainedText, ...], BeforeValidator(coerce_tuple)]
    reviewer_recommendation: ReviewerRecommendation

    @model_validator(mode="after")
    def _check_review_report_invariants(self) -> "ReviewReport":
        if self.review_id != self.artifact_id:
            raise ValueError("review_id must equal the envelope artifact_id")
        if (
            self.reviewer.actor_type != self.producer.actor_type
            or self.reviewer.actor_id != self.producer.actor_id
        ):
            raise ValueError("reviewer actor_id and actor_type must match the envelope producer")
        if (
            self.independence.satisfied
            and self.reviewer.actor_id == self.independence.executor_actor_id
        ):
            raise ValueError(
                "independence.satisfied requires reviewer.actor_id to differ "
                "from independence.executor_actor_id"
            )
        finding_ids = [f.finding_id for f in self.findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("finding_id values must be unique across the review report")
        return self


__all__ = [
    "ReviewReport",
    "ReviewerIdentity",
    "ReviewIndependence",
    "ReviewSubject",
    "ReviewedFile",
    "ReviewInputs",
    "FileFindingLocation",
    "ArtifactFindingLocation",
    "GeneralFindingLocation",
    "FindingLocation",
    "Finding",
]
