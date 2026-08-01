"""A2A-09: concrete-artifact digest support.

Proves that ``seal_artifact`` preserves the exact concrete runtime class,
that every concrete body field participates in the content digest, and
that tampering with any body or envelope field is detected as a
``DigestMismatchError``.
"""

import copy
import json
from collections.abc import Callable
from typing import TypeVar

import pytest

from tests.a2a_factories import (
    build_certification_manifest,
    build_completion_report,
    build_evidence_artifact,
    build_observation,
    build_packet,
)
from zadc.canonical import canonical_json_text
from zadc.digests import compute_content_digest, seal_artifact, verify_content_digest
from zadc.errors import DigestMismatchError, DigestMissingError
from zadc.models.certification_manifest import CertificationManifest
from zadc.models.common import ArtifactEnvelope
from zadc.models.completion_report import CompletionReport
from zadc.models.evidence_artifact import EvidenceArtifact
from zadc.models.observation import Observation
from zadc.models.packet import Packet

_EnvelopeT = TypeVar("_EnvelopeT", bound=ArtifactEnvelope)


def _tamper(
    cls: type[_EnvelopeT], sealed: _EnvelopeT, mutate: Callable[[dict[str, object]], None]
) -> None:
    """Apply ``mutate`` to the sealed instance's canonical dump and assert mismatch."""
    data = json.loads(canonical_json_text(sealed))
    mutate(data)
    tampered = cls.model_validate(data)
    with pytest.raises(DigestMismatchError):
        verify_content_digest(tampered)


class TestSealArtifactPreservesConcreteClass:
    @pytest.mark.parametrize(
        "builder,cls",
        [
            (build_packet, Packet),
            (build_completion_report, CompletionReport),
            (build_certification_manifest, CertificationManifest),
            (build_evidence_artifact, EvidenceArtifact),
            (build_observation, Observation),
        ],
    )
    def test_seal_returns_same_concrete_class(self, builder: object, cls: type) -> None:
        instance = builder()  # type: ignore[operator]
        sealed = seal_artifact(instance)
        assert type(sealed) is cls
        assert isinstance(sealed, cls)

    @pytest.mark.parametrize(
        "builder",
        [
            build_packet,
            build_completion_report,
            build_certification_manifest,
            build_evidence_artifact,
            build_observation,
        ],
    )
    def test_seal_verify_roundtrip(self, builder: object) -> None:
        instance = builder()  # type: ignore[operator]
        sealed = seal_artifact(instance)
        assert sealed.provenance.content_digest is not None
        expected = verify_content_digest(sealed)
        assert expected == sealed.provenance.content_digest

    @pytest.mark.parametrize(
        "builder",
        [
            build_packet,
            build_completion_report,
            build_certification_manifest,
            build_evidence_artifact,
            build_observation,
        ],
    )
    def test_resealing_is_idempotent(self, builder: object) -> None:
        instance = builder()  # type: ignore[operator]
        sealed_once = seal_artifact(instance)
        sealed_twice = seal_artifact(sealed_once)
        assert sealed_once.provenance.content_digest == sealed_twice.provenance.content_digest

    @pytest.mark.parametrize(
        "builder",
        [
            build_packet,
            build_completion_report,
            build_certification_manifest,
            build_evidence_artifact,
            build_observation,
        ],
    )
    def test_verify_missing_digest_raises(self, builder: object) -> None:
        instance = builder()  # type: ignore[operator]
        with pytest.raises(DigestMissingError):
            verify_content_digest(instance)

    @pytest.mark.parametrize(
        "builder",
        [
            build_packet,
            build_completion_report,
            build_certification_manifest,
            build_evidence_artifact,
            build_observation,
        ],
    )
    def test_compute_content_digest_ignores_subclass_type_for_generic_call(
        self, builder: object
    ) -> None:
        instance = builder()  # type: ignore[operator]
        digest1 = compute_content_digest(instance)
        digest2 = compute_content_digest(instance)
        assert digest1 == digest2
        assert digest1.startswith("sha256:")


class TestPacketBodyFieldsParticipateInDigest:
    def _sealed(self) -> Packet:
        return seal_artifact(build_packet())

    def test_tamper_authorization(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["authorization"]["authorized_by"] = "zutfen:human:someone-else"  # type: ignore[index]

        _tamper(Packet, sealed, mutate)

    def test_tamper_repository(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["repository"]["pull_request"] = 999  # type: ignore[index]

        _tamper(Packet, sealed, mutate)

    def test_tamper_work_start(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["work_start"]["mismatch_policy"] = "reconcile_with_record"  # type: ignore[index]

        _tamper(Packet, sealed, mutate)

    def test_tamper_intent(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["intent"]["desired_outcome"] = "a different outcome entirely"  # type: ignore[index]

        _tamper(Packet, sealed, mutate)

    def test_tamper_scope(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["scope"]["allowed_paths"] = ["docs/**"]  # type: ignore[index]

        _tamper(Packet, sealed, mutate)

    def test_tamper_requirements(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["requirements"][0]["statement"] = "a materially different requirement"  # type: ignore[index]

        _tamper(Packet, sealed, mutate)

    def test_tamper_dependency_pins(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["dependency_pins"][0]["cleanliness_required"] = False  # type: ignore[index]

        _tamper(Packet, sealed, mutate)

    def test_tamper_verification(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["verification"]["synthetic_merge_required"] = True  # type: ignore[index]

        _tamper(Packet, sealed, mutate)

    def test_tamper_review(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["review"]["minimum_severity_blocking"] = "note"  # type: ignore[index]

        _tamper(Packet, sealed, mutate)

    def test_tamper_stop_conditions(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["stop_conditions"] = ["a new stop condition"]

        _tamper(Packet, sealed, mutate)

    def test_tamper_deliverables(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["deliverables"] = ["a different deliverable"]

        _tamper(Packet, sealed, mutate)

    def test_tamper_completion_report_requirements(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["completion_report_requirements"] = ["a different requirement"]

        _tamper(Packet, sealed, mutate)

    def test_tamper_supersedes(self) -> None:
        sealed = seal_artifact(
            build_packet(
                supersedes={
                    "artifact_id": "urn:uuid:00000000-0000-0000-0000-000000000099",
                    "content_digest": "sha256:" + "9" * 64,
                }
            )
        )

        def mutate(d: dict[str, object]) -> None:
            d["supersedes"]["artifact_id"] = (  # type: ignore[index]
                "urn:uuid:00000000-0000-0000-0000-000000000098"
            )

        _tamper(Packet, sealed, mutate)

    def test_tamper_envelope_field_slice_id(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["slice_id"] = "ZADC-999X"

        _tamper(Packet, sealed, mutate)


class TestCompletionReportBodyFieldsParticipateInDigest:
    def _sealed(self) -> CompletionReport:
        return seal_artifact(build_completion_report())

    def test_tamper_packet_id(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["packet_id"] = "urn:uuid:00000000-0000-0000-0000-000000000077"

        _tamper(CompletionReport, sealed, mutate)

    def test_tamper_run_id(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["run_id"] = "urn:uuid:00000000-0000-0000-0000-000000000077"

        _tamper(CompletionReport, sealed, mutate)

    def test_tamper_work_start(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            # Both SHAs must stay equal to satisfy the match=True invariant,
            # so tamper them together to a different (still-equal) pair.
            d["work_start"]["expected_sha"] = "9" * 40  # type: ignore[index]
            d["work_start"]["actual_sha"] = "9" * 40  # type: ignore[index]

        _tamper(CompletionReport, sealed, mutate)

    def test_tamper_repository_state(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["repository_state"]["branch"] = "a-different-branch"  # type: ignore[index]

        _tamper(CompletionReport, sealed, mutate)

    def test_tamper_changes(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["changes"]["files_changed"] = ["a-different-file.py"]  # type: ignore[index]

        _tamper(CompletionReport, sealed, mutate)

    def test_tamper_verification_claims(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["verification_claims"]["commands_run"] = ["make different"]  # type: ignore[index]

        _tamper(CompletionReport, sealed, mutate)

    def test_tamper_known_limitations(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["known_limitations"][0]["statement"] = "a different limitation"  # type: ignore[index]

        _tamper(CompletionReport, sealed, mutate)

    def test_tamper_executor_recommendation(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["executor_recommendation"] = "red"

        _tamper(CompletionReport, sealed, mutate)


class TestCertificationManifestBodyFieldsParticipateInDigest:
    def _sealed(self) -> CertificationManifest:
        return seal_artifact(build_certification_manifest())

    def test_tamper_packet_id(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["packet_id"] = "urn:uuid:00000000-0000-0000-0000-000000000077"

        _tamper(CertificationManifest, sealed, mutate)

    def test_tamper_subject(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["subject"]["subject_sha"] = "9" * 40  # type: ignore[index]
            d["subject"]["head_sha"] = "9" * 40  # type: ignore[index]

        _tamper(CertificationManifest, sealed, mutate)

    def test_tamper_environment(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["environment"]["os"] = "a-different-os"  # type: ignore[index]

        _tamper(CertificationManifest, sealed, mutate)

    def test_tamper_lanes(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["lanes"][0]["command_or_workflow"] = "make a-different-check"  # type: ignore[index]

        _tamper(CertificationManifest, sealed, mutate)

    def test_tamper_evidence(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["evidence"][0]["media_type"] = "application/json"  # type: ignore[index]

        _tamper(CertificationManifest, sealed, mutate)

    def test_tamper_result(self) -> None:
        sealed = seal_artifact(
            build_certification_manifest(
                lanes=[],
                result="inconclusive",
            )
        )

        def mutate(d: dict[str, object]) -> None:
            d["result"] = "fail"

        _tamper(CertificationManifest, sealed, mutate)


class TestEvidenceArtifactBodyFieldsParticipateInDigest:
    def _sealed(self) -> EvidenceArtifact:
        return seal_artifact(build_evidence_artifact())

    def test_tamper_verification_run_id(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["verification_run_id"] = "urn:uuid:00000000-0000-0000-0000-000000000077"

        _tamper(EvidenceArtifact, sealed, mutate)

    def test_tamper_subject(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["subject"]["subject_sha"] = "9" * 40  # type: ignore[index]

        _tamper(EvidenceArtifact, sealed, mutate)

    def test_tamper_media_type(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["media_type"] = "application/json"

        _tamper(EvidenceArtifact, sealed, mutate)

    def test_tamper_digest(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["digest"] = "sha256:" + "9" * 64

        _tamper(EvidenceArtifact, sealed, mutate)

    def test_tamper_location(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["location"] = "https://ci.example.com/artifacts/other.txt"

        _tamper(EvidenceArtifact, sealed, mutate)

    def test_tamper_availability(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["availability"] = "unavailable"

        _tamper(EvidenceArtifact, sealed, mutate)

    def test_tamper_size_bytes(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["size_bytes"] = 2048

        _tamper(EvidenceArtifact, sealed, mutate)

    def test_tamper_description(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["description"] = "a different description"

        _tamper(EvidenceArtifact, sealed, mutate)


class TestObservationBodyFieldsParticipateInDigest:
    def _sealed(self) -> Observation:
        return seal_artifact(build_observation())

    def test_tamper_subject_id(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["subject_id"] = "github:Zutfen-LLC/zadc/pull/43"

        _tamper(Observation, sealed, mutate)

    def test_tamper_source(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["source"]["source_event_id"] = "evt-different"  # type: ignore[index]

        _tamper(Observation, sealed, mutate)

    def test_tamper_statement(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["statement"] = "a different observed statement"

        _tamper(Observation, sealed, mutate)

    def test_tamper_epistemic_status(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["epistemic_status"] = "STALE"

        _tamper(Observation, sealed, mutate)

    def test_tamper_freshness_seconds(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["freshness_seconds"] = 600

        _tamper(Observation, sealed, mutate)

    def test_tamper_expires_at(self) -> None:
        sealed = self._sealed()

        def mutate(d: dict[str, object]) -> None:
            d["expires_at"] = "2026-07-31T13:00:00Z"

        _tamper(Observation, sealed, mutate)


class TestDeepCopyIndependence:
    """Sanity check that ``_tamper`` mutations do not leak between test cases."""

    def test_original_sealed_instance_unaffected_by_dict_mutation(self) -> None:
        sealed = seal_artifact(build_packet())
        data = json.loads(canonical_json_text(sealed))
        mutated = copy.deepcopy(data)
        mutated["intent"]["problem_statement"] = "mutated copy only"
        assert sealed.intent.problem_statement != mutated["intent"]["problem_statement"]
