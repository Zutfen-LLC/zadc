"""The CompletionReport artifact: the execution agent's self-reported claims.

Implements architecture section 11.2. A completion report records what the
execution agent claims and locally observed — it is evidence of a claim,
not proof (architecture section 5.3, "claims are not facts"). Material
statements use the shared :class:`~zadc.models.shared.ExecutorClaim` model,
which defaults to epistemic status ``AGENT_REPORTED`` and is never
automatically promoted to a stronger status by this model.
"""

from typing import Annotated, Literal, Optional

from pydantic import BeforeValidator, Field, model_validator

from zadc.models.common import ArtifactEnvelope, _ZadcModel
from zadc.models.shared import ExecutorClaim
from zadc.types import (
    ConstrainedText,
    ExecutorRecommendation,
    GitSha,
    GlobalId,
    RefName,
    coerce_tuple,
)


class ReconciliationCommit(_ZadcModel):
    """One intervening commit enumerated by a work-start reconciliation record."""

    sha: GitSha
    disposition: ConstrainedText
    rationale: ConstrainedText


class Reconciliation(_ZadcModel):
    """Enumerates intervening commits when the observed work-start SHA does
    not match the packet's expected work-start SHA (architecture 13, INV-002).

    ``intervening_commits`` MUST be non-empty — an empty reconciliation
    would satisfy the presence gate on :class:`WorkStartObservation` without
    actually enumerating any commit, defeating the INV-002 accountability
    requirement. ``minItems: 1`` is schema-model-owned via ``Field``.

    ``uniqueItems`` is emitted as a best-effort schema signal (it rejects
    fully identical entries), but JSON Schema cannot express "no duplicate
    ``sha`` across items with otherwise-differing disposition/rationale" —
    that narrower sha-uniqueness invariant is enforced at runtime only,
    by :meth:`_check_unique_shas`.
    """

    intervening_commits: Annotated[
        tuple[ReconciliationCommit, ...], BeforeValidator(coerce_tuple)
    ] = Field(min_length=1, json_schema_extra={"uniqueItems": True})

    @model_validator(mode="after")
    def _check_unique_shas(self) -> "Reconciliation":
        shas = [commit.sha for commit in self.intervening_commits]
        if len(shas) != len(set(shas)):
            raise ValueError("intervening_commits must not contain duplicate SHAs")
        return self


class WorkStartObservation(_ZadcModel):
    """The observed work-start SHA versus the packet's expected SHA."""

    expected_sha: GitSha
    actual_sha: GitSha
    match: bool
    reconciliation: Optional[Reconciliation] = None

    @model_validator(mode="after")
    def _check_match_invariants(self) -> "WorkStartObservation":
        expected_match = self.expected_sha == self.actual_sha
        if self.match != expected_match:
            raise ValueError("match must equal (expected_sha == actual_sha)")
        if self.match and self.reconciliation is not None:
            raise ValueError("a matching work-start must not carry a reconciliation record")
        if not self.match and self.reconciliation is None:
            raise ValueError("a work-start mismatch requires a reconciliation record")
        return self


class RepositoryState(_ZadcModel):
    """The observed repository state at completion-report time."""

    repository_id: GlobalId
    base_sha: GitSha
    implementation_sha: GitSha
    pr_head_sha_observed: Optional[GitSha] = None
    branch: RefName


class DependencyPinResolution(_ZadcModel):
    """The observed resolution of one packet-declared dependency pin."""

    repository_id: GlobalId
    sha: GitSha
    clean: bool


class Changes(_ZadcModel):
    """The set of commits, changed files, and resolved dependency pins."""

    commits: Annotated[tuple[GitSha, ...], BeforeValidator(coerce_tuple)]
    files_changed: Annotated[tuple[ConstrainedText, ...], BeforeValidator(coerce_tuple)]
    dependency_pins_resolved: Annotated[
        tuple[DependencyPinResolution, ...], BeforeValidator(coerce_tuple)
    ]

    @model_validator(mode="after")
    def _check_no_duplicates(self) -> "Changes":
        if len(self.commits) != len(set(self.commits)):
            raise ValueError("commits must not contain duplicate SHAs")
        if len(self.files_changed) != len(set(self.files_changed)):
            raise ValueError("files_changed must not contain duplicate paths")
        return self


class VerificationClaims(_ZadcModel):
    """The executor-reported local verification commands and results."""

    commands_run: Annotated[tuple[ConstrainedText, ...], BeforeValidator(coerce_tuple)]
    local_results: Annotated[tuple[ExecutorClaim, ...], BeforeValidator(coerce_tuple)]


class CompletionReport(ArtifactEnvelope):
    """The execution agent's completion claim (architecture section 11.2)."""

    artifact_type: Literal["completion_report"]

    packet_id: GlobalId
    run_id: GlobalId
    work_start: WorkStartObservation
    repository_state: RepositoryState
    changes: Changes
    verification_claims: VerificationClaims
    deviations: Annotated[tuple[ExecutorClaim, ...], BeforeValidator(coerce_tuple)]
    known_limitations: Annotated[tuple[ExecutorClaim, ...], BeforeValidator(coerce_tuple)]
    open_issues: Annotated[tuple[ExecutorClaim, ...], BeforeValidator(coerce_tuple)]
    executor_recommendation: ExecutorRecommendation


__all__ = [
    "CompletionReport",
    "ReconciliationCommit",
    "Reconciliation",
    "WorkStartObservation",
    "RepositoryState",
    "DependencyPinResolution",
    "Changes",
    "VerificationClaims",
]
