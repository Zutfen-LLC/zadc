"""A2B2: the WorkflowBundle artifact and its supporting models.

Covers construction/invariant enforcement (workflow_bundle_runtime in the
packet's test matrix) and digest sealing/canonicalization
(digest_and_canonical) for WorkflowBundle, AgentRunReference, BundleBlocker,
and DerivedStateSnapshot.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from tests.a2b2_factories import (
    DIGEST_C,
    EXECUTOR_ID,
    VALIDATOR_ID,
    VALIDATOR_RUN_ID,
    WORKFLOW_BUNDLE_ID,
    build_minimal_workflow_bundle,
    build_workflow_bundle,
    sealed_ref,
)
from zadc import Provenance
from zadc.canonical import canonical_json_text
from zadc.digests import compute_content_digest, seal_artifact, verify_content_digest
from zadc.errors import DigestMismatchError
from zadc.models.shared import ArtifactReference
from zadc.models.workflow_bundle import (
    AgentRunReference,
    BundleBlocker,
    DerivedStateSnapshot,
    WorkflowBundle,
)


def _self_ref() -> ArtifactReference:
    return ArtifactReference(artifact_id=WORKFLOW_BUNDLE_ID, content_digest=DIGEST_C)


def _replace_derived_state(bundle: WorkflowBundle, **overrides: object) -> DerivedStateSnapshot:
    ds = bundle.derived_state
    base: dict[str, object] = {
        "state": ds.state,
        "computed_at": ds.computed_at,
        "validator_actor_id": ds.validator_actor_id,
        "validator_run_id": ds.validator_run_id,
        "policy": ds.policy,
        "input_artifact_refs": ds.input_artifact_refs,
        "blockers": ds.blockers,
        "stale_artifact_refs": ds.stale_artifact_refs,
        "next_admissible_actions": ds.next_admissible_actions,
    }
    base.update(overrides)
    return DerivedStateSnapshot(**base)  # type: ignore[arg-type]


class TestWorkflowBundleConstruction:
    def test_valid_minimal_bundle(self) -> None:
        bundle = build_minimal_workflow_bundle()
        assert bundle.artifact_type == "workflow_bundle"
        assert bundle.bundle_id == bundle.artifact_id
        assert bundle.completion_report_refs == ()
        assert bundle.agent_run_refs == ()

    def test_valid_populated_bundle(self) -> None:
        bundle = build_workflow_bundle()
        assert len(bundle.agent_run_refs) == 1
        assert len(bundle.completion_report_refs) == 1
        assert len(bundle.derived_state.blockers) == 1

    def test_rejects_wrong_artifact_type(self) -> None:
        with pytest.raises(ValidationError):
            build_workflow_bundle(artifact_type="packet")

    def test_rejects_extra_top_level_field(self) -> None:
        with pytest.raises(ValidationError):
            build_workflow_bundle(unexpected_field="nope")

    def test_frozen(self) -> None:
        bundle = build_workflow_bundle()
        with pytest.raises(ValidationError):
            bundle.bundle_id = "urn:uuid:00000000-0000-0000-0000-000000000999"

    def test_list_and_tuple_inputs_are_equivalent(self) -> None:
        run_ref = AgentRunReference(
            run_id="urn:uuid:00000000-0000-0000-0000-000000000950", executor_actor_id=EXECUTOR_ID
        )
        as_list = build_workflow_bundle(agent_run_refs=[run_ref])
        as_tuple = build_workflow_bundle(agent_run_refs=(run_ref,))
        assert as_list.agent_run_refs == as_tuple.agent_run_refs == (run_ref,)
        assert isinstance(as_list.agent_run_refs, tuple)

    def test_derived_state_list_inputs_normalize_to_tuple(self) -> None:
        bundle = build_workflow_bundle()
        ds = bundle.derived_state
        as_list = DerivedStateSnapshot(
            state=ds.state,
            computed_at=ds.computed_at,
            validator_actor_id=ds.validator_actor_id,
            validator_run_id=ds.validator_run_id,
            policy=ds.policy,
            input_artifact_refs=list(ds.input_artifact_refs),  # type: ignore[arg-type]
            blockers=list(ds.blockers),  # type: ignore[arg-type]
            stale_artifact_refs=list(ds.stale_artifact_refs),  # type: ignore[arg-type]
            next_admissible_actions=list(ds.next_admissible_actions),  # type: ignore[arg-type]
        )
        assert isinstance(as_list.input_artifact_refs, tuple)
        assert isinstance(as_list.blockers, tuple)
        assert isinstance(as_list.stale_artifact_refs, tuple)
        assert isinstance(as_list.next_admissible_actions, tuple)

    def test_bundle_id_must_equal_artifact_id(self) -> None:
        with pytest.raises(ValidationError, match="bundle_id"):
            build_workflow_bundle(bundle_id="urn:uuid:00000000-0000-0000-0000-000000000999")


class TestAgentRunReferences:
    def test_duplicate_run_ids_rejected(self) -> None:
        run_ref = AgentRunReference(
            run_id="urn:uuid:00000000-0000-0000-0000-000000000950", executor_actor_id=EXECUTOR_ID
        )
        with pytest.raises(ValidationError, match="run_id"):
            build_workflow_bundle(agent_run_refs=(run_ref, run_ref))

    def test_optional_fields_default_none(self) -> None:
        run_ref = AgentRunReference(
            run_id="urn:uuid:00000000-0000-0000-0000-000000000950", executor_actor_id=EXECUTOR_ID
        )
        assert run_ref.framework is None
        assert run_ref.model is None
        assert run_ref.provider is None


class TestBundleBlocker:
    def test_valid(self) -> None:
        ref = sealed_ref(build_workflow_bundle())
        blocker = BundleBlocker(
            blocker_id="B-1", code="missing-x", statement="x is missing", artifact_refs=(ref,)
        )
        assert blocker.blocker_id == "B-1"

    def test_duplicate_artifact_refs_rejected(self) -> None:
        ref = ArtifactReference(
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000600", content_digest=DIGEST_C
        )
        with pytest.raises(ValidationError, match="artifact_refs"):
            BundleBlocker(blocker_id="B-1", code="x", statement="x", artifact_refs=(ref, ref))


class TestDerivedStateSnapshot:
    def _kwargs(self, **overrides: object) -> dict[str, object]:
        bundle = build_workflow_bundle()
        base: dict[str, object] = {
            "state": "pending",
            "computed_at": datetime(2026, 8, 1, 12, 30, 0, tzinfo=UTC),
            "validator_actor_id": VALIDATOR_ID,
            "validator_run_id": VALIDATOR_RUN_ID,
            "policy": bundle.policy,
            "input_artifact_refs": (),
            "blockers": (),
            "stale_artifact_refs": (),
            "next_admissible_actions": (),
        }
        base.update(overrides)
        return base

    def test_valid(self) -> None:
        snapshot = DerivedStateSnapshot(**self._kwargs())  # type: ignore[arg-type]
        assert snapshot.state == "pending"

    def test_duplicate_input_artifact_refs_rejected(self) -> None:
        ref = ArtifactReference(
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000601", content_digest=DIGEST_C
        )
        with pytest.raises(ValidationError, match="input_artifact_refs"):
            DerivedStateSnapshot(**self._kwargs(input_artifact_refs=(ref, ref)))  # type: ignore[arg-type]

    def test_duplicate_stale_artifact_refs_rejected(self) -> None:
        ref = ArtifactReference(
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000602", content_digest=DIGEST_C
        )
        with pytest.raises(ValidationError, match="stale_artifact_refs"):
            DerivedStateSnapshot(**self._kwargs(stale_artifact_refs=(ref, ref)))  # type: ignore[arg-type]

    def test_duplicate_blocker_ids_rejected(self) -> None:
        blocker = BundleBlocker(blocker_id="B-DUP", code="x", statement="x", artifact_refs=())
        with pytest.raises(ValidationError, match="blocker_id"):
            DerivedStateSnapshot(**self._kwargs(blockers=(blocker, blocker)))  # type: ignore[arg-type]

    def test_duplicate_next_admissible_actions_rejected(self) -> None:
        with pytest.raises(ValidationError, match="next_admissible_actions"):
            DerivedStateSnapshot(**self._kwargs(next_admissible_actions=("submit", "submit")))  # type: ignore[arg-type]


class TestWorkflowBundleSelfReferenceRejected:
    def test_packet_ref_self_reference_rejected(self) -> None:
        with pytest.raises(ValidationError, match="own artifact_id"):
            build_workflow_bundle(packet_ref=_self_ref())

    def test_completion_report_refs_self_reference_rejected(self) -> None:
        with pytest.raises(ValidationError, match="own artifact_id"):
            build_workflow_bundle(completion_report_refs=(_self_ref(),))

    def test_certification_manifest_refs_self_reference_rejected(self) -> None:
        with pytest.raises(ValidationError, match="own artifact_id"):
            build_workflow_bundle(certification_manifest_refs=(_self_ref(),))

    def test_evidence_artifact_refs_self_reference_rejected(self) -> None:
        with pytest.raises(ValidationError, match="own artifact_id"):
            build_workflow_bundle(evidence_artifact_refs=(_self_ref(),))

    def test_review_report_refs_self_reference_rejected(self) -> None:
        with pytest.raises(ValidationError, match="own artifact_id"):
            build_workflow_bundle(review_report_refs=(_self_ref(),))

    def test_decision_record_refs_self_reference_rejected(self) -> None:
        with pytest.raises(ValidationError, match="own artifact_id"):
            build_workflow_bundle(decision_record_refs=(_self_ref(),))

    def test_observation_refs_self_reference_rejected(self) -> None:
        with pytest.raises(ValidationError, match="own artifact_id"):
            build_workflow_bundle(observation_refs=(_self_ref(),))

    def test_supersedes_bundle_ref_self_reference_rejected(self) -> None:
        with pytest.raises(ValidationError, match="own artifact_id"):
            build_workflow_bundle(
                supersedes_bundle_ref=_self_ref(),
                provenance=Provenance(parent_artifact_ids=(WORKFLOW_BUNDLE_ID,)),
            )

    def test_derived_state_input_artifact_refs_self_reference_rejected(self) -> None:
        base = build_workflow_bundle()
        new_ds = _replace_derived_state(base, input_artifact_refs=(_self_ref(),))
        with pytest.raises(ValidationError, match="own artifact_id"):
            build_workflow_bundle(derived_state=new_ds)

    def test_derived_state_blocker_artifact_refs_self_reference_rejected(self) -> None:
        base = build_workflow_bundle()
        blocker = BundleBlocker(
            blocker_id="B-SELF", code="self-ref", statement="self ref", artifact_refs=(_self_ref(),)
        )
        new_ds = _replace_derived_state(base, blockers=(blocker,))
        with pytest.raises(ValidationError, match="own artifact_id"):
            build_workflow_bundle(derived_state=new_ds)

    def test_derived_state_stale_artifact_refs_self_reference_rejected(self) -> None:
        base = build_workflow_bundle()
        new_ds = _replace_derived_state(base, stale_artifact_refs=(_self_ref(),))
        with pytest.raises(ValidationError, match="own artifact_id"):
            build_workflow_bundle(derived_state=new_ds)


class TestWorkflowBundleCollectionConsistency:
    def test_duplicate_ids_within_typed_collection_rejected(self) -> None:
        bundle = build_workflow_bundle()
        cert_ref = bundle.certification_manifest_refs[0]
        with pytest.raises(ValidationError, match="top-level"):
            build_workflow_bundle(certification_manifest_refs=(cert_ref, cert_ref))

    def test_same_id_across_typed_collections_rejected(self) -> None:
        bundle = build_workflow_bundle()
        completion_ref = bundle.completion_report_refs[0]
        with pytest.raises(ValidationError, match="top-level"):
            build_workflow_bundle(certification_manifest_refs=(completion_ref,))

    def test_same_id_with_conflicting_digest_rejected(self) -> None:
        bundle = build_workflow_bundle()
        cert_ref = bundle.certification_manifest_refs[0]
        conflicting = ArtifactReference(artifact_id=cert_ref.artifact_id, content_digest=DIGEST_C)
        assert conflicting.content_digest != cert_ref.content_digest
        with pytest.raises(ValidationError, match="conflicting content_digest"):
            build_workflow_bundle(certification_manifest_refs=(cert_ref, conflicting))

    def test_derived_state_reference_absent_from_top_level_rejected(self) -> None:
        base = build_workflow_bundle()
        stray = ArtifactReference(
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000700", content_digest=DIGEST_C
        )
        new_ds = _replace_derived_state(
            base, input_artifact_refs=(*base.derived_state.input_artifact_refs, stray)
        )
        with pytest.raises(ValidationError, match="top-level artifact references"):
            build_workflow_bundle(derived_state=new_ds)

    def test_derived_state_digest_mismatch_rejected(self) -> None:
        base = build_workflow_bundle()
        packet_ref = base.packet_ref
        mismatched = ArtifactReference(artifact_id=packet_ref.artifact_id, content_digest=DIGEST_C)
        assert mismatched.content_digest != packet_ref.content_digest
        new_ds = _replace_derived_state(base, input_artifact_refs=(mismatched,))
        with pytest.raises(ValidationError, match="conflicting content_digest"):
            build_workflow_bundle(derived_state=new_ds)

    def test_blocker_artifact_ref_absent_from_top_level_rejected(self) -> None:
        base = build_workflow_bundle()
        stray = ArtifactReference(
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000701", content_digest=DIGEST_C
        )
        blocker = BundleBlocker(blocker_id="B-2", code="x", statement="x", artifact_refs=(stray,))
        new_ds = _replace_derived_state(base, blockers=(blocker,))
        with pytest.raises(ValidationError, match="top-level artifact references"):
            build_workflow_bundle(derived_state=new_ds)

    def test_stale_artifact_ref_absent_from_top_level_rejected(self) -> None:
        base = build_workflow_bundle()
        stray = ArtifactReference(
            artifact_id="urn:uuid:00000000-0000-0000-0000-000000000702", content_digest=DIGEST_C
        )
        new_ds = _replace_derived_state(base, stale_artifact_refs=(stray,))
        with pytest.raises(ValidationError, match="top-level artifact references"):
            build_workflow_bundle(derived_state=new_ds)


class TestWorkflowBundleDerivedStatePolicy:
    def test_policy_mismatch_rejected(self) -> None:
        base = build_workflow_bundle()
        from zadc import PolicyReference

        other_policy = PolicyReference(
            policy_id="zutfen:zadc-policy:other@0.1.0",
            policy_source_sha=base.policy.policy_source_sha,
            policy_digest=base.policy.policy_digest,
        )
        new_ds = _replace_derived_state(base, policy=other_policy)
        with pytest.raises(ValidationError, match="policy"):
            build_workflow_bundle(derived_state=new_ds)


class TestWorkflowBundleSupersession:
    def test_absent_from_provenance_rejected(self) -> None:
        other_id = "urn:uuid:00000000-0000-0000-0000-000000000800"
        other_ref = ArtifactReference(artifact_id=other_id, content_digest=DIGEST_C)
        with pytest.raises(ValidationError, match="provenance.parent_artifact_ids"):
            build_workflow_bundle(supersedes_bundle_ref=other_ref)

    def test_valid_supersession_lineage(self) -> None:
        other_id = "urn:uuid:00000000-0000-0000-0000-000000000800"
        other_ref = ArtifactReference(artifact_id=other_id, content_digest=DIGEST_C)
        bundle = build_workflow_bundle(
            supersedes_bundle_ref=other_ref,
            provenance=Provenance(parent_artifact_ids=(other_id,)),
        )
        assert bundle.supersedes_bundle_ref is not None
        assert bundle.supersedes_bundle_ref.artifact_id == other_id


class TestWorkflowBundleProvenanceSelfParentRejected:
    """MAJOR-1: a bundle must not be its own provenance parent.

    ``Provenance.parent_artifact_ids`` accepts arbitrary parent IDs at the
    shared model level; ``WorkflowBundle`` must independently reject the
    case where its own ``artifact_id`` appears among them, regardless of
    whether any typed reference collection also self-references (those are
    checked separately by ``_check_workflow_bundle_invariants``'s ``all_refs``
    loop and do not cover ``provenance.parent_artifact_ids`` at all).
    """

    def test_bundle_id_as_sole_parent_rejected(self) -> None:
        with pytest.raises(ValidationError, match="parent_artifact_ids"):
            build_workflow_bundle(provenance=Provenance(parent_artifact_ids=(WORKFLOW_BUNDLE_ID,)))

    def test_bundle_id_among_multiple_parents_rejected(self) -> None:
        other_id = "urn:uuid:00000000-0000-0000-0000-000000000801"
        with pytest.raises(ValidationError, match="parent_artifact_ids"):
            build_workflow_bundle(
                provenance=Provenance(parent_artifact_ids=(other_id, WORKFLOW_BUNDLE_ID))
            )

    def test_distinct_parent_ids_still_accepted(self) -> None:
        other_id = "urn:uuid:00000000-0000-0000-0000-000000000802"
        bundle = build_workflow_bundle(provenance=Provenance(parent_artifact_ids=(other_id,)))
        assert bundle.provenance.parent_artifact_ids == (other_id,)


class TestWorkflowBundleDerivedStateChronology:
    """MAJOR-2: an immutable bundle must not carry a derived-state snapshot
    computed after the bundle's own declared creation time."""

    def test_computed_at_after_created_at_rejected(self) -> None:
        base = build_workflow_bundle()
        new_ds = _replace_derived_state(base, computed_at=base.created_at + timedelta(minutes=1))
        with pytest.raises(ValidationError, match="computed_at"):
            build_workflow_bundle(derived_state=new_ds)

    def test_computed_at_equal_created_at_accepted(self) -> None:
        base = build_workflow_bundle()
        new_ds = _replace_derived_state(base, computed_at=base.created_at)
        bundle = build_workflow_bundle(derived_state=new_ds)
        assert bundle.derived_state.computed_at == bundle.created_at

    def test_computed_at_before_created_at_accepted(self) -> None:
        base = build_workflow_bundle()
        new_ds = _replace_derived_state(base, computed_at=base.created_at - timedelta(minutes=1))
        bundle = build_workflow_bundle(derived_state=new_ds)
        assert bundle.derived_state.computed_at < bundle.created_at


class TestWorkflowBundleDigestSealingAndCanonicalization:
    def test_seal_preserves_concrete_class(self) -> None:
        bundle = build_workflow_bundle()
        sealed = seal_artifact(bundle)
        assert type(sealed) is WorkflowBundle
        assert sealed.provenance.content_digest is not None

    def test_verify_content_digest_roundtrip(self) -> None:
        sealed = seal_artifact(build_workflow_bundle())
        verify_content_digest(sealed)

    def test_tamper_top_level_field_detected(self) -> None:
        sealed = seal_artifact(build_workflow_bundle())
        data = json.loads(canonical_json_text(sealed))
        data["project_id"] = "zutfen:project:different"
        tampered = WorkflowBundle.model_validate(data)
        with pytest.raises(DigestMismatchError):
            verify_content_digest(tampered)

    def test_tamper_typed_reference_detected(self) -> None:
        sealed = seal_artifact(build_workflow_bundle())
        data = json.loads(canonical_json_text(sealed))
        data["evidence_artifact_refs"] = [dict(data["evidence_artifact_refs"][0])]
        data["evidence_artifact_refs"][0]["content_digest"] = DIGEST_C
        tampered = WorkflowBundle.model_validate(data)
        with pytest.raises(DigestMismatchError):
            verify_content_digest(tampered)

    def test_tamper_derived_state_detected(self) -> None:
        sealed = seal_artifact(build_workflow_bundle())
        data = json.loads(canonical_json_text(sealed))
        data["derived_state"] = dict(data["derived_state"])
        data["derived_state"]["state"] = "a-different-state"
        tampered = WorkflowBundle.model_validate(data)
        with pytest.raises(DigestMismatchError):
            verify_content_digest(tampered)

    def test_tamper_blocker_detected(self) -> None:
        sealed = seal_artifact(build_workflow_bundle())
        data = json.loads(canonical_json_text(sealed))
        data["derived_state"] = dict(data["derived_state"])
        data["derived_state"]["blockers"] = [dict(data["derived_state"]["blockers"][0])]
        data["derived_state"]["blockers"][0]["statement"] = "a different blocker statement"
        tampered = WorkflowBundle.model_validate(data)
        with pytest.raises(DigestMismatchError):
            verify_content_digest(tampered)

    def test_tamper_policy_detected(self) -> None:
        sealed = seal_artifact(build_workflow_bundle())
        data = json.loads(canonical_json_text(sealed))
        data["policy"] = dict(data["policy"])
        data["derived_state"] = dict(data["derived_state"])
        data["derived_state"]["policy"] = dict(data["derived_state"]["policy"])
        new_sha = "f" * 40
        data["policy"]["policy_source_sha"] = new_sha
        data["derived_state"]["policy"]["policy_source_sha"] = new_sha
        tampered = WorkflowBundle.model_validate(data)
        with pytest.raises(DigestMismatchError):
            verify_content_digest(tampered)

    def test_tamper_supersession_detected(self) -> None:
        other_id = "urn:uuid:00000000-0000-0000-0000-000000000800"
        other_ref = ArtifactReference(artifact_id=other_id, content_digest=DIGEST_C)
        bundle = build_workflow_bundle(
            supersedes_bundle_ref=other_ref,
            provenance=Provenance(parent_artifact_ids=(other_id,)),
        )
        sealed = seal_artifact(bundle)
        data = json.loads(canonical_json_text(sealed))
        data["supersedes_bundle_ref"] = dict(data["supersedes_bundle_ref"])
        data["supersedes_bundle_ref"]["content_digest"] = "sha256:" + "9" * 64
        tampered = WorkflowBundle.model_validate(data)
        with pytest.raises(DigestMismatchError):
            verify_content_digest(tampered)

    def test_canonical_round_trip_reload(self) -> None:
        sealed = seal_artifact(build_workflow_bundle())
        data = json.loads(canonical_json_text(sealed))
        reloaded = WorkflowBundle.model_validate(data)
        assert reloaded == sealed
        verify_content_digest(reloaded)

    def test_canonical_output_invariant_across_list_and_tuple_input(self) -> None:
        run_ref = AgentRunReference(
            run_id="urn:uuid:00000000-0000-0000-0000-000000000951", executor_actor_id=EXECUTOR_ID
        )
        as_list = build_workflow_bundle(agent_run_refs=[run_ref])
        as_tuple = build_workflow_bundle(agent_run_refs=(run_ref,))
        assert compute_content_digest(as_list) == compute_content_digest(as_tuple)

    def test_canonical_output_invariant_across_field_order(self) -> None:
        bundle = build_workflow_bundle()
        kwargs = bundle.model_dump(mode="python", by_alias=True)
        reordered_kwargs = dict(reversed(list(kwargs.items())))
        reordered = WorkflowBundle.model_validate(reordered_kwargs)
        assert compute_content_digest(bundle) == compute_content_digest(reordered)
