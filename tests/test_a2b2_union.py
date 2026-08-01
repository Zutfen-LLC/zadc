"""A2B2: the global ZadcArtifact discriminated union and validation adapter."""

import json
from typing import cast

import pytest
from pydantic import ValidationError

from tests.a2a_factories import (
    build_certification_manifest,
    build_completion_report,
    build_evidence_artifact,
    build_observation,
    build_packet,
)
from tests.a2b1_factories import build_decision_record, build_review_report
from tests.a2b2_factories import build_workflow_bundle
from zadc.canonical import canonical_json_text
from zadc.digests import seal_artifact
from zadc.models.artifact_union import (
    ZADC_ARTIFACT_ADAPTER,
    ZadcArtifact,
    validate_artifact,
    validate_artifact_json,
)
from zadc.models.certification_manifest import CertificationManifest
from zadc.models.completion_report import CompletionReport
from zadc.models.decision_record import DecisionRecord
from zadc.models.evidence_artifact import EvidenceArtifact
from zadc.models.observation import Observation
from zadc.models.packet import Packet
from zadc.models.review_report import ReviewReport
from zadc.models.workflow_bundle import WorkflowBundle

_VARIANT_TABLE = [
    (Packet, build_packet),
    (CompletionReport, build_completion_report),
    (CertificationManifest, build_certification_manifest),
    (EvidenceArtifact, build_evidence_artifact),
    (Observation, build_observation),
    (ReviewReport, build_review_report),
    (DecisionRecord, build_decision_record),
    (WorkflowBundle, build_workflow_bundle),
]


def _sealed_data(builder: object) -> dict[str, object]:
    sealed = seal_artifact(builder())  # type: ignore[operator]
    return dict(json.loads(canonical_json_text(sealed)))


class TestZadcArtifactDispatchesAllVariants:
    @pytest.mark.parametrize("cls,builder", _VARIANT_TABLE)
    def test_validate_artifact_returns_exact_concrete_class(
        self, cls: type, builder: object
    ) -> None:
        data = _sealed_data(builder)
        result = validate_artifact(data)
        assert type(result) is cls
        assert result.artifact_type == data["artifact_type"]

    @pytest.mark.parametrize("cls,builder", _VARIANT_TABLE)
    def test_validate_artifact_json_text_returns_exact_concrete_class(
        self, cls: type, builder: object
    ) -> None:
        sealed = seal_artifact(builder())  # type: ignore[operator]
        text = canonical_json_text(sealed)
        result = validate_artifact_json(text)
        assert type(result) is cls

    @pytest.mark.parametrize("cls,builder", _VARIANT_TABLE)
    def test_validate_artifact_json_bytes_returns_exact_concrete_class(
        self, cls: type, builder: object
    ) -> None:
        sealed = seal_artifact(builder())  # type: ignore[operator]
        text_bytes = canonical_json_text(sealed).encode("utf-8")
        result = validate_artifact_json(text_bytes)
        assert type(result) is cls

    @pytest.mark.parametrize("cls,builder", _VARIANT_TABLE)
    def test_adapter_validate_python_matches_public_function(
        self, cls: type, builder: object
    ) -> None:
        data = _sealed_data(builder)
        adapter_result = ZADC_ARTIFACT_ADAPTER.validate_python(data)
        assert type(adapter_result) is cls


class TestZadcArtifactRejectsBadDiscriminators:
    def test_unknown_artifact_type_rejected(self) -> None:
        data = _sealed_data(build_packet)
        data["artifact_type"] = "not_a_real_artifact_type"
        with pytest.raises(ValidationError):
            validate_artifact(data)

    def test_missing_artifact_type_rejected(self) -> None:
        data = _sealed_data(build_packet)
        del data["artifact_type"]
        with pytest.raises(ValidationError):
            validate_artifact(data)

    def test_null_artifact_type_rejected(self) -> None:
        data = _sealed_data(build_packet)
        data["artifact_type"] = None
        with pytest.raises(ValidationError):
            validate_artifact(data)

    def test_non_mapping_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate_artifact("not a mapping")


class TestZadcArtifactRejectsBodyDiscriminatorMismatch:
    def test_workflow_bundle_body_with_packet_discriminator_rejected(self) -> None:
        data = _sealed_data(build_workflow_bundle)
        data["artifact_type"] = "packet"
        with pytest.raises(ValidationError):
            validate_artifact(data)

    def test_packet_body_with_workflow_bundle_discriminator_rejected(self) -> None:
        data = _sealed_data(build_packet)
        data["artifact_type"] = "workflow_bundle"
        with pytest.raises(ValidationError):
            validate_artifact(data)


class TestZadcArtifactRejectsCrossVariantFields:
    def test_packet_payload_with_workflow_bundle_only_field_rejected(self) -> None:
        data = _sealed_data(build_packet)
        # bundle_id belongs only to WorkflowBundle; Packet is extra="forbid".
        data["bundle_id"] = "urn:uuid:00000000-0000-0000-0000-000000000999"
        with pytest.raises(ValidationError):
            validate_artifact(data)

    def test_workflow_bundle_payload_with_packet_only_field_rejected(self) -> None:
        data = _sealed_data(build_workflow_bundle)
        # authorization belongs only to Packet; WorkflowBundle is extra="forbid".
        data["authorization"] = {
            "authorized_by": "zutfen:human:eric",
            "authorized_at": "2026-07-31T11:00:00Z",
        }
        with pytest.raises(ValidationError):
            validate_artifact(data)


class TestZadcArtifactRejectsWorkflowBundleSelfParentProvenance:
    """MAJOR-1 regression: the global union entrypoint must reject a
    WorkflowBundle payload whose own artifact_id appears in
    provenance.parent_artifact_ids, exactly as direct construction does —
    proving the check fires along the ``validate_artifact``/
    ``validate_artifact_json`` dispatch path, not merely on direct
    ``WorkflowBundle(...)`` construction."""

    def _data_with_self_parent_provenance(self) -> dict[str, object]:
        data = _sealed_data(build_workflow_bundle)
        provenance: dict[str, object] = dict(cast(dict[str, object], data["provenance"]))
        provenance["parent_artifact_ids"] = [data["artifact_id"]]
        data["provenance"] = provenance
        return data

    def test_self_parent_provenance_rejected_via_validate_artifact(self) -> None:
        data = self._data_with_self_parent_provenance()
        with pytest.raises(ValidationError, match="parent_artifact_ids"):
            validate_artifact(data)

    def test_self_parent_provenance_rejected_via_validate_artifact_json(self) -> None:
        data = self._data_with_self_parent_provenance()
        text = json.dumps(data)
        with pytest.raises(ValidationError, match="parent_artifact_ids"):
            validate_artifact_json(text)


class TestZadcArtifactTypeExport:
    def test_zadc_artifact_is_annotated_union(self) -> None:
        # Sanity: the type alias is importable and usable as a type annotation.
        assert ZadcArtifact is not None
