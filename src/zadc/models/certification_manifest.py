"""The CertificationManifest artifact: trusted results bound to an exact subject.

Implements architecture section 11.3. Produced by trusted CI or a trusted
local verifier — never by the execution agent itself. Binds lane results
and evidence to an exact commit subject. The manifest's certification
policy reference reuses the inherited ``ArtifactEnvelope.policy`` field;
this model does not add a second, potentially conflicting top-level policy
field.

This model does not prove that every packet-required lane is present —
cross-artifact reconciliation between a packet's declared mandatory lanes
and a manifest's actual lanes is deferred to a later validation slice.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator

from zadc.models.common import ArtifactEnvelope, _ZadcModel
from zadc.models.shared import EvidenceReference, ExactSubject, VerificationEnvironment
from zadc.types import (
    CertificationResult,
    ConstrainedText,
    GlobalId,
    LaneClassification,
    LaneConclusion,
    StableId,
    Timestamp,
    coerce_tuple,
)


def _certification_manifest_json_schema_extra(
    schema: dict[str, Any], model: type[BaseModel]
) -> None:
    """Model-owned hook surfacing the result/mandatory-lane pass gate.

    JSON Schema can express "when result is pass, every mandatory lane
    item's conclusion is pass" via a nested per-item ``if``/``then`` inside
    ``lanes.items``. It cannot express lane_id uniqueness (no cross-item
    "unique by field" primitive in Draft 2020-12) — that remains
    runtime-only, enforced by
    ``CertificationManifest._check_manifest_invariants``.
    """
    schema["allOf"] = [
        {
            "if": {
                "properties": {"result": {"const": "pass"}},
                "required": ["result"],
            },
            "then": {
                "properties": {
                    "lanes": {
                        "items": {
                            "if": {
                                "properties": {"classification": {"const": "mandatory"}},
                                "required": ["classification"],
                            },
                            "then": {"properties": {"conclusion": {"const": "pass"}}},
                        }
                    }
                }
            },
        }
    ]


class LaneResult(_ZadcModel):
    """The result of one verification lane run."""

    lane_id: StableId
    classification: LaneClassification
    conclusion: LaneConclusion
    started_at: Timestamp
    completed_at: Timestamp
    command_or_workflow: ConstrainedText
    evidence_refs: Annotated[tuple[EvidenceReference, ...], BeforeValidator(coerce_tuple)]

    @model_validator(mode="after")
    def _check_lane_time(self) -> "LaneResult":
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        return self


class CertificationManifest(ArtifactEnvelope):
    """Trusted verification results bound to an exact subject (architecture 11.3)."""

    model_config = ConfigDict(json_schema_extra=_certification_manifest_json_schema_extra)

    artifact_type: Literal["certification_manifest"]

    packet_id: GlobalId
    run_id: GlobalId
    subject: ExactSubject
    environment: VerificationEnvironment
    lanes: Annotated[tuple[LaneResult, ...], BeforeValidator(coerce_tuple)]
    evidence: Annotated[tuple[EvidenceReference, ...], BeforeValidator(coerce_tuple)]
    result: CertificationResult

    @model_validator(mode="after")
    def _check_manifest_invariants(self) -> "CertificationManifest":
        lane_ids = [lane.lane_id for lane in self.lanes]
        if len(lane_ids) != len(set(lane_ids)):
            raise ValueError("lane_id values must be unique across the manifest")
        if self.result == "pass":
            for lane in self.lanes:
                if lane.classification == "mandatory" and lane.conclusion != "pass":
                    raise ValueError(
                        "result cannot be 'pass' while a mandatory lane did not pass "
                        f"(lane_id={lane.lane_id!r}, conclusion={lane.conclusion!r})"
                    )
        return self


__all__ = [
    "CertificationManifest",
    "LaneResult",
]
