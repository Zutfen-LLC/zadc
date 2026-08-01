"""Shared supporting models reused across A2A concrete artifacts.

These models back the "shared enums and references" and "exact verification
subjects" surfaces from architecture sections 9-14: they are reused by more
than one concrete artifact body (:mod:`zadc.models.packet`,
:mod:`zadc.models.completion_report`, :mod:`zadc.models.certification_manifest`,
:mod:`zadc.models.evidence_artifact`, :mod:`zadc.models.observation`). None
of these models is itself a top-level ZADC artifact envelope — they are
always nested inside a concrete artifact's body.
"""

from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator

from zadc.models.common import _ZadcModel
from zadc.types import (
    ConstrainedText,
    EpistemicStatus,
    GitSha,
    GlobalId,
    MediaType,
    ObservationSourceType,
    Sha256Digest,
    SubjectKind,
    coerce_tuple,
)


def _exact_subject_json_schema_extra(schema: dict[str, Any], model: type[BaseModel]) -> None:
    """Model-owned hook surfacing the subject-kind presence gates.

    JSON Schema can express that ``pr_head``/``synthetic_merge`` REQUIRE
    their supporting SHA fields to be present. It cannot express that
    ``head_sha`` (or ``synthetic_merge_sha``) EQUALS ``subject_sha`` — a
    comparison between two arbitrary sibling string values is outside
    standard JSON Schema's vocabulary. Those equality checks remain
    runtime-only, enforced by ``ExactSubject._check_subject_kind_invariants``.
    """
    schema["allOf"] = [
        {
            "if": {
                "properties": {"subject_kind": {"const": "pr_head"}},
                "required": ["subject_kind"],
            },
            "then": {"required": ["head_sha"]},
        },
        {
            "if": {
                "properties": {"subject_kind": {"const": "synthetic_merge"}},
                "required": ["subject_kind"],
            },
            "then": {"required": ["base_sha", "head_sha", "synthetic_merge_sha"]},
        },
    ]


class ArtifactReference(_ZadcModel):
    """A reference to another canonical ZADC artifact by ID and content digest.

    Distinct from :class:`EvidenceReference`, which points at an external,
    non-ZADC evidence payload rather than another sealed ZADC artifact.
    """

    artifact_id: GlobalId
    content_digest: Sha256Digest


class EvidenceReference(_ZadcModel):
    """A pointer to an external evidence payload (architecture section 11.3).

    Carries the evidence identifier, its media type, the payload's own
    SHA-256 digest, and a trusted URI/provider location. This is a
    lightweight, denormalized reference distinct from a full
    :class:`~zadc.models.evidence_artifact.EvidenceArtifact` record — it
    does not carry availability, size, or a description.
    """

    artifact_id: GlobalId
    media_type: MediaType
    digest: Sha256Digest
    location: GlobalId


class ExactSubject(_ZadcModel):
    """The exact commit subject a verification run or evidence item targets.

    Shared by :class:`~zadc.models.certification_manifest.CertificationManifest`
    and :class:`~zadc.models.evidence_artifact.EvidenceArtifact` (A2A-07).
    This model records the claimed subject identity only; it does not
    inspect Git ancestry or diff content.
    """

    model_config = ConfigDict(json_schema_extra=_exact_subject_json_schema_extra)

    repository_id: GlobalId
    subject_kind: SubjectKind
    subject_sha: GitSha
    base_sha: Optional[GitSha] = None
    head_sha: Optional[GitSha] = None
    synthetic_merge_sha: Optional[GitSha] = None

    @model_validator(mode="after")
    def _check_subject_kind_invariants(self) -> "ExactSubject":
        if self.subject_kind == "pr_head" and self.head_sha != self.subject_sha:
            raise ValueError("a pr_head subject requires head_sha to equal subject_sha")
        if self.subject_kind == "synthetic_merge":
            if self.base_sha is None or self.head_sha is None or self.synthetic_merge_sha is None:
                raise ValueError(
                    "a synthetic_merge subject requires base_sha, head_sha, "
                    "and synthetic_merge_sha to all be present"
                )
            if self.synthetic_merge_sha != self.subject_sha:
                raise ValueError(
                    "a synthetic_merge subject requires subject_sha to equal synthetic_merge_sha"
                )
        return self


class VerificationEnvironment(_ZadcModel):
    """The trusted execution environment for a certification run (architecture 11.3)."""

    runner_identity: GlobalId
    os: ConstrainedText
    architecture: ConstrainedText
    toolchain: Annotated[tuple[ConstrainedText, ...], BeforeValidator(coerce_tuple)]
    container_digests: Annotated[tuple[Sha256Digest, ...], BeforeValidator(coerce_tuple)]


class ObservationSource(_ZadcModel):
    """The identity of the live source an :class:`~zadc.models.observation.Observation`
    was drawn from (architecture section 8.14)."""

    source_type: ObservationSourceType
    source_id: GlobalId
    source_event_id: Optional[ConstrainedText] = None


class ExecutorClaim(_ZadcModel):
    """A material statement authored by an execution agent (architecture section 12).

    Defaults to ``AGENT_REPORTED`` epistemic status. Construction never
    automatically promotes a claim to ``VERIFIED`` or any stronger status —
    upgrading epistemic status requires evidence or human judgment applied
    by a later validation slice, not this model.
    """

    statement: ConstrainedText
    epistemic_status: EpistemicStatus = "AGENT_REPORTED"
    evidence_refs: Annotated[tuple[EvidenceReference, ...], BeforeValidator(coerce_tuple)]


__all__ = [
    "ArtifactReference",
    "EvidenceReference",
    "ExactSubject",
    "VerificationEnvironment",
    "ObservationSource",
    "ExecutorClaim",
]
