"""The DecisionRecord artifact: an authenticated human decision claim.

Implements architecture sections 8-14 (A2B1). A decision record captures
what a human decision-maker claims to have decided, and about what exact
subject. A structurally valid ``DecisionRecord`` does **not** authenticate
its human identity and does **not** confer merge authorization until a
later trusted validator binds the identity and verifies policy and live
repository state (deferred to a later slice; see
``docs/api-a2b1-review-decision-artifacts.md``).

This model deliberately does not require ``decision_subject_sha`` to equal
``current_pr_head_sha_observed`` — freshness and live-head reconciliation
are out of scope here. It also does not query GitHub or authenticate the
claimed human identity beyond the internal-consistency check against the
envelope producer (see :class:`DecisionRecord`).
"""

from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, PositiveInt, model_validator

from zadc.models.common import ArtifactEnvelope, _ZadcModel
from zadc.models.shared import ArtifactReference
from zadc.types import (
    ConstrainedText,
    DecisionType,
    GitSha,
    GlobalId,
    StableId,
    Timestamp,
    coerce_tuple,
)

#: Forbids the ``null`` branch of an Optional field's ``anyOf`` schema.
#: ``required`` alone only checks key presence — canonical serialization
#: always includes optional fields as ``null`` rather than omitting them,
#: so a presence gate alone would not reject an explicit ``null`` bypass.
_NOT_NULL: dict[str, Any] = {"not": {"type": "null"}}


class HumanDecisionIdentity(_ZadcModel):
    """The claimed human identity that authored a :class:`DecisionRecord`.

    ``actor_type`` is fixed to ``human`` — a decision record can never be
    produced by an agent, CI, validator, or service actor. This model
    records the claimed identity only; authenticating it against a trusted
    identity provider is deferred to a later validation slice.
    """

    actor_type: Literal["human"]
    actor_id: GlobalId


class DecisionSubject(_ZadcModel):
    """The exact subject a :class:`DecisionRecord` claims to decide about.

    ``decision_subject_sha`` and ``current_pr_head_sha_observed`` are not
    required to match at model construction — freshness and live-head
    reconciliation between the decided-upon subject and the repository's
    current state are deferred to a later validation slice. This model
    does not query GitHub or verify either SHA against a live source.
    """

    repository_id: GlobalId
    pull_request: PositiveInt
    decision_subject_sha: GitSha
    current_pr_head_sha_observed: GitSha
    review_report_ids: Annotated[tuple[GlobalId, ...], BeforeValidator(coerce_tuple)]
    certification_manifest_ids: Annotated[tuple[GlobalId, ...], BeforeValidator(coerce_tuple)]

    @model_validator(mode="after")
    def _check_unique_ids(self) -> "DecisionSubject":
        if len(self.review_report_ids) != len(set(self.review_report_ids)):
            raise ValueError("review_report_ids must not contain duplicate values")
        if len(self.certification_manifest_ids) != len(set(self.certification_manifest_ids)):
            raise ValueError("certification_manifest_ids must not contain duplicate values")
        return self


class AcceptedRisk(_ZadcModel):
    """One finding a human decision-maker has explicitly accepted as risk.

    ``expires_at``, when present, must be later than the enclosing
    :class:`DecisionRecord`'s ``decided_at`` — a comparison against a
    sibling artifact-level field enforced by ``DecisionRecord`` itself
    (not by this model in isolation), and one with no standard JSON Schema
    vocabulary; it is documented as a runtime-only invariant (see
    ``docs/api-a2b1-review-decision-artifacts.md``).
    """

    finding_id: StableId
    rationale: ConstrainedText
    scope: ConstrainedText
    expires_at: Optional[Timestamp] = None


def _decision_record_json_schema_extra(schema: dict[str, Any], model: type[BaseModel]) -> None:
    """Model-owned hook surfacing the decision-specific presence/count gates.

    JSON Schema can express, independently for each of the two
    decision-specific fields:

    - ``decision == "accept_risk"`` requires ``accepted_risks`` to have at
      least one item, and every other decision requires it to be empty
      (two independent ``if``/``then`` blocks, keyed on the positive and
      negated ``decision`` conditions).
    - ``decision == "supersede"`` requires ``supersedes_decision_ref`` to
      be present and non-null, and every other decision requires it to be
      exactly ``null`` (two further independent ``if``/``then`` blocks).

    It cannot express that ``supersedes_decision_ref.artifact_id`` differs
    from this artifact's own ``artifact_id`` — that comparison has no
    standard JSON Schema vocabulary and remains runtime-only, enforced by
    ``DecisionRecord._check_decision_record_invariants``.
    """
    not_accept_risk = {
        "not": {
            "properties": {"decision": {"const": "accept_risk"}},
            "required": ["decision"],
        }
    }
    not_supersede = {
        "not": {
            "properties": {"decision": {"const": "supersede"}},
            "required": ["decision"],
        }
    }
    schema["allOf"] = [
        {
            "if": {
                "properties": {"decision": {"const": "accept_risk"}},
                "required": ["decision"],
            },
            "then": {"properties": {"accepted_risks": {"minItems": 1}}},
        },
        {
            "if": not_accept_risk,
            "then": {"properties": {"accepted_risks": {"maxItems": 0}}},
        },
        {
            "if": {
                "properties": {"decision": {"const": "supersede"}},
                "required": ["decision"],
            },
            "then": {
                "required": ["supersedes_decision_ref"],
                "properties": {"supersedes_decision_ref": _NOT_NULL},
            },
        },
        {
            "if": not_supersede,
            "then": {"properties": {"supersedes_decision_ref": {"type": "null"}}},
        },
    ]


class DecisionRecord(ArtifactEnvelope):
    """An authenticated human decision claim (architecture A2B1).

    A structurally valid ``DecisionRecord`` does not, by itself, authenticate
    its human identity and does not confer merge authorization — a later
    trusted validator must bind the identity and verify policy and live
    repository state. This model enforces only internal structural
    consistency: the envelope producer must claim to be the same human
    identity as ``decided_by``, and the decision-specific field gates below
    must hold.
    """

    model_config = ConfigDict(json_schema_extra=_decision_record_json_schema_extra)

    artifact_type: Literal["decision_record"]

    decision_id: GlobalId
    decided_by: HumanDecisionIdentity
    decided_at: Timestamp
    subject: DecisionSubject
    decision: DecisionType
    accepted_risks: Annotated[tuple[AcceptedRisk, ...], BeforeValidator(coerce_tuple)]
    supersedes_decision_ref: Optional[ArtifactReference] = None
    conditions: Annotated[tuple[ConstrainedText, ...], BeforeValidator(coerce_tuple)]
    rationale: ConstrainedText

    @model_validator(mode="after")
    def _check_decision_record_invariants(self) -> "DecisionRecord":
        if self.decision_id != self.artifact_id:
            raise ValueError("decision_id must equal the envelope artifact_id")
        if (
            self.producer.actor_type != "human"
            or self.producer.actor_id != self.decided_by.actor_id
        ):
            raise ValueError(
                "the envelope producer must have actor_type='human' and actor_id "
                "equal to decided_by.actor_id"
            )
        if self.decision == "accept_risk":
            if len(self.accepted_risks) == 0:
                raise ValueError("decision='accept_risk' requires at least one accepted risk")
        elif len(self.accepted_risks) != 0:
            raise ValueError(f"decision={self.decision!r} requires accepted_risks to be empty")
        if self.decision == "supersede":
            if self.supersedes_decision_ref is None:
                raise ValueError("decision='supersede' requires a non-null supersedes_decision_ref")
        elif self.supersedes_decision_ref is not None:
            raise ValueError(
                f"decision={self.decision!r} requires supersedes_decision_ref to be null"
            )
        if (
            self.supersedes_decision_ref is not None
            and self.supersedes_decision_ref.artifact_id == self.artifact_id
        ):
            raise ValueError("supersedes_decision_ref.artifact_id must not equal this artifact_id")
        risk_ids = [risk.finding_id for risk in self.accepted_risks]
        if len(risk_ids) != len(set(risk_ids)):
            raise ValueError(
                "accepted-risk finding_id values must be unique within the decision record"
            )
        for risk in self.accepted_risks:
            if risk.expires_at is not None and risk.expires_at <= self.decided_at:
                raise ValueError("AcceptedRisk.expires_at must be later than decided_at")
        return self


__all__ = [
    "DecisionRecord",
    "HumanDecisionIdentity",
    "DecisionSubject",
    "AcceptedRisk",
]
