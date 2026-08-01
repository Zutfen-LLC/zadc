"""The WorkflowBundle artifact: the canonical aggregate for a slice instance.

Implements architecture sections 8.15 and 11.6 (A2B2). A workflow bundle
links the authorized packet, agent runs, completion reports, certification
manifests, review reports, decision records, and observations for one slice
instance by stable ID and content digest, and carries a recorded
``derived_state`` snapshot.

This model enforces only internal, structural consistency: that the
bundle's own identity, its typed reference collections, and its
``derived_state`` are mutually coherent. It does **not** compute or
recompute lifecycle state, evaluate policy, resolve external references,
or verify that a referenced artifact_id actually resolves to a sealed
artifact of the claimed type — see ``docs/api-a2b2-workflow-bundle-union.md``
for the full trust-boundary statement.

``DerivedStateSnapshot`` is recorded validator output, carried by the
bundle as a claim. This model does not prove that its ``state``,
``blockers``, ``stale_artifact_refs``, or ``next_admissible_actions`` are
correct, and does not recompute them from the referenced artifacts.
"""

from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from zadc.models.common import ArtifactEnvelope, PolicyReference, _ZadcModel
from zadc.models.shared import ArtifactReference
from zadc.types import ConstrainedText, GlobalId, StableId, Timestamp, coerce_tuple


def _check_artifact_refs_duplicate_free(
    refs: tuple[ArtifactReference, ...], field_name: str
) -> None:
    """Shared runtime check: an ArtifactReference tuple must be duplicate-free by artifact_id.

    Reused by :class:`BundleBlocker` and :class:`DerivedStateSnapshot` —
    each of their ``ArtifactReference``-typed collections is checked the
    same way. This does not compare content digests within the tuple; a
    single tuple carrying the same ``artifact_id`` twice is rejected
    regardless of whether the digests happen to match.
    """
    ids = [ref.artifact_id for ref in refs]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{field_name} must not contain duplicate artifact_id values")


class AgentRunReference(_ZadcModel):
    """An identity claim about one agent run that participated in a slice instance.

    Records identity claims only — ``run_id``, ``executor_actor_id``, and
    the optional ``framework``/``model``/``provider`` fields are exactly
    what is claimed by whoever assembled the bundle. This is not a
    top-level artifact: it carries no content digest, and this model does
    not authenticate the run, the actor, the framework, the model, or the
    provider.
    """

    run_id: GlobalId
    executor_actor_id: GlobalId
    framework: Optional[ConstrainedText] = None
    model: Optional[ConstrainedText] = None
    provider: Optional[ConstrainedText] = None


class BundleBlocker(_ZadcModel):
    """One structural blocker surfaced by a bundle's recorded derived state.

    A blocker is structural derived-state output — a recorded claim about
    what is blocking, and why, with supporting artifact references. It is
    **not** a :class:`~zadc.models.review_report.Finding` and not a new
    authority-bearing artifact. This model does not implement blocker
    severity, finding closure, or policy thresholds.
    """

    blocker_id: StableId
    code: StableId
    statement: ConstrainedText
    artifact_refs: Annotated[tuple[ArtifactReference, ...], BeforeValidator(coerce_tuple)] = Field(
        json_schema_extra={"uniqueItems": True}
    )

    @model_validator(mode="after")
    def _check_artifact_refs(self) -> "BundleBlocker":
        _check_artifact_refs_duplicate_free(self.artifact_refs, "artifact_refs")
        return self


class DerivedStateSnapshot(_ZadcModel):
    """A recorded snapshot of validator-computed derived state for a bundle.

    ``state`` is an opaque stable identifier in this slice — not a
    lifecycle enum defined here. ``validator_actor_id`` and
    ``validator_run_id`` are claims recorded by the bundle; no trust
    binding is performed against them. This model does not prove that its
    ``state``, ``blockers``, ``stale_artifact_refs``, or
    ``next_admissible_actions`` are correct — it only records what a
    validator reported, structurally self-consistent within the snapshot.
    Cross-checking these references against the enclosing bundle's
    top-level artifact references is performed by
    :class:`~zadc.models.workflow_bundle.WorkflowBundle`, not by this
    model in isolation.
    """

    state: StableId
    computed_at: Timestamp
    validator_actor_id: GlobalId
    validator_run_id: GlobalId
    policy: PolicyReference
    input_artifact_refs: Annotated[tuple[ArtifactReference, ...], BeforeValidator(coerce_tuple)] = (
        Field(json_schema_extra={"uniqueItems": True})
    )
    blockers: Annotated[tuple[BundleBlocker, ...], BeforeValidator(coerce_tuple)]
    stale_artifact_refs: Annotated[tuple[ArtifactReference, ...], BeforeValidator(coerce_tuple)] = (
        Field(json_schema_extra={"uniqueItems": True})
    )
    next_admissible_actions: Annotated[tuple[StableId, ...], BeforeValidator(coerce_tuple)] = Field(
        json_schema_extra={"uniqueItems": True}
    )

    @model_validator(mode="after")
    def _check_derived_state_invariants(self) -> "DerivedStateSnapshot":
        _check_artifact_refs_duplicate_free(self.input_artifact_refs, "input_artifact_refs")
        _check_artifact_refs_duplicate_free(self.stale_artifact_refs, "stale_artifact_refs")
        blocker_ids = [blocker.blocker_id for blocker in self.blockers]
        if len(blocker_ids) != len(set(blocker_ids)):
            raise ValueError("blockers must not contain duplicate blocker_id values")
        if len(self.next_admissible_actions) != len(set(self.next_admissible_actions)):
            raise ValueError("next_admissible_actions must not contain duplicate values")
        return self


#: The names of the WorkflowBundle's mutually-exclusive top-level typed
#: artifact-reference collections, in declaration order. ``packet_ref`` is
#: singular but participates in the same cross-collection exclusivity and
#: digest-consistency checks as the six tuple collections.
_TOP_LEVEL_REF_COLLECTIONS: tuple[str, ...] = (
    "completion_report_refs",
    "certification_manifest_refs",
    "evidence_artifact_refs",
    "review_report_refs",
    "decision_record_refs",
    "observation_refs",
)


def _workflow_bundle_json_schema_extra(schema: dict[str, Any], model: type[BaseModel]) -> None:
    """Model-owned hook surfacing the supersession-requires-parent-lineage gate.

    JSON Schema can express that a non-null ``supersedes_bundle_ref`` requires
    ``provenance.parent_artifact_ids`` to be non-empty (``minItems: 1``) via a
    single ``if``/``then`` block. It cannot express that the exact
    ``supersedes_bundle_ref.artifact_id`` value is a *member* of
    ``parent_artifact_ids`` — a membership check against a sibling tuple's
    element values — which remains runtime-only, enforced by
    :meth:`WorkflowBundle._check_workflow_bundle_invariants`.
    """
    schema["allOf"] = [
        {
            "if": {
                "properties": {"supersedes_bundle_ref": {"not": {"type": "null"}}},
                "required": ["supersedes_bundle_ref"],
            },
            "then": {
                "properties": {
                    "provenance": {"properties": {"parent_artifact_ids": {"minItems": 1}}}
                },
                "required": ["provenance"],
            },
        },
    ]


class WorkflowBundle(ArtifactEnvelope):
    """The canonical aggregate for one slice instance (architecture 8.15, 11.6).

    Links the authorized packet, agent runs, and every downstream artifact
    produced for a slice instance by stable ID and content digest, plus a
    recorded ``derived_state`` snapshot. A bundle MUST NOT override the
    contents of referenced artifacts — it never embeds full artifacts in
    this slice, and it does not verify that a referenced ``artifact_id``
    actually resolves to a sealed artifact of the collection's claimed
    type (that referential-integrity check is deferred to a later
    validation slice).
    """

    model_config = ConfigDict(json_schema_extra=_workflow_bundle_json_schema_extra)

    artifact_type: Literal["workflow_bundle"]

    bundle_id: GlobalId
    packet_ref: ArtifactReference
    agent_run_refs: Annotated[tuple[AgentRunReference, ...], BeforeValidator(coerce_tuple)]
    completion_report_refs: Annotated[
        tuple[ArtifactReference, ...], BeforeValidator(coerce_tuple)
    ] = Field(json_schema_extra={"uniqueItems": True})
    certification_manifest_refs: Annotated[
        tuple[ArtifactReference, ...], BeforeValidator(coerce_tuple)
    ] = Field(json_schema_extra={"uniqueItems": True})
    evidence_artifact_refs: Annotated[
        tuple[ArtifactReference, ...], BeforeValidator(coerce_tuple)
    ] = Field(json_schema_extra={"uniqueItems": True})
    review_report_refs: Annotated[tuple[ArtifactReference, ...], BeforeValidator(coerce_tuple)] = (
        Field(json_schema_extra={"uniqueItems": True})
    )
    decision_record_refs: Annotated[
        tuple[ArtifactReference, ...], BeforeValidator(coerce_tuple)
    ] = Field(json_schema_extra={"uniqueItems": True})
    observation_refs: Annotated[tuple[ArtifactReference, ...], BeforeValidator(coerce_tuple)] = (
        Field(json_schema_extra={"uniqueItems": True})
    )
    supersedes_bundle_ref: Optional[ArtifactReference] = None
    derived_state: DerivedStateSnapshot

    @model_validator(mode="after")
    def _check_workflow_bundle_invariants(self) -> "WorkflowBundle":
        if self.bundle_id != self.artifact_id:
            raise ValueError("bundle_id must equal the envelope artifact_id")
        if self.artifact_id in self.provenance.parent_artifact_ids:
            raise ValueError(
                "provenance.parent_artifact_ids must not contain the WorkflowBundle's own "
                "artifact_id"
            )
        if self.derived_state.computed_at > self.created_at:
            raise ValueError(
                "derived_state.computed_at must not be later than the WorkflowBundle's created_at"
            )
        if self.policy != self.derived_state.policy:
            raise ValueError("derived_state.policy must equal the WorkflowBundle envelope policy")

        run_ids = [ref.run_id for ref in self.agent_run_refs]
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("agent_run_refs must not contain duplicate run_id values")

        top_level_refs: list[tuple[str, ArtifactReference]] = [("packet_ref", self.packet_ref)]
        for name in _TOP_LEVEL_REF_COLLECTIONS:
            top_level_refs.extend((name, ref) for ref in getattr(self, name))

        derived_refs: list[tuple[str, ArtifactReference]] = []
        if self.supersedes_bundle_ref is not None:
            derived_refs.append(("supersedes_bundle_ref", self.supersedes_bundle_ref))
        derived_refs.extend(
            ("derived_state.input_artifact_refs", ref)
            for ref in self.derived_state.input_artifact_refs
        )
        for blocker in self.derived_state.blockers:
            derived_refs.extend(
                (f"derived_state.blockers[{blocker.blocker_id}].artifact_refs", ref)
                for ref in blocker.artifact_refs
            )
        derived_refs.extend(
            ("derived_state.stale_artifact_refs", ref)
            for ref in self.derived_state.stale_artifact_refs
        )

        all_refs = top_level_refs + derived_refs

        for name, ref in all_refs:
            if ref.artifact_id == self.artifact_id:
                raise ValueError(f"{name} must not reference the WorkflowBundle's own artifact_id")

        digest_by_id: dict[str, str] = {}
        for name, ref in all_refs:
            seen_digest = digest_by_id.get(ref.artifact_id)
            if seen_digest is not None and seen_digest != ref.content_digest:
                raise ValueError(
                    f"artifact_id {ref.artifact_id!r} appears with conflicting content_digest "
                    f"values in the bundle (at {name})"
                )
            digest_by_id[ref.artifact_id] = ref.content_digest

        top_level_digest_by_id: dict[str, str] = {}
        for _name, ref in top_level_refs:
            if ref.artifact_id in top_level_digest_by_id:
                raise ValueError(
                    f"artifact_id {ref.artifact_id!r} must not appear in more than one "
                    "top-level typed artifact-reference collection"
                )
            top_level_digest_by_id[ref.artifact_id] = ref.content_digest

        for name, ref in derived_refs:
            if name == "supersedes_bundle_ref":
                continue
            if ref.artifact_id not in top_level_digest_by_id:
                raise ValueError(
                    f"{name} artifact_id {ref.artifact_id!r} must match an artifact_id "
                    "and content_digest present in the bundle's top-level artifact references"
                )

        if (
            self.supersedes_bundle_ref is not None
            and self.supersedes_bundle_ref.artifact_id not in self.provenance.parent_artifact_ids
        ):
            raise ValueError(
                "supersedes_bundle_ref.artifact_id must appear in provenance.parent_artifact_ids"
            )

        return self


__all__ = [
    "WorkflowBundle",
    "AgentRunReference",
    "BundleBlocker",
    "DerivedStateSnapshot",
]
