"""A2A-10: data-driven schema export for the envelope and all five A2A artifacts.

Proves: each committed schema is a valid Draft 2020-12 schema; each schema
accepts a representative valid sealed artifact and rejects representative
invalid variants (missing required fields, wrong consts/enums, bad
identifiers/timestamps/ranges, nested extra properties); regeneration is
byte-identical (``git diff`` would be empty); and the exported schema
differs from the raw model schema only by approved document metadata and
key ordering.
"""

import copy
import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from tests.a2a_factories import (
    build_certification_manifest,
    build_completion_report,
    build_evidence_artifact,
    build_observation,
    build_packet,
)
from zadc.canonical import canonical_json_text
from zadc.digests import seal_artifact
from zadc.models.certification_manifest import CertificationManifest
from zadc.models.completion_report import CompletionReport
from zadc.models.evidence_artifact import EvidenceArtifact
from zadc.models.observation import Observation
from zadc.models.packet import Packet

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_schemas import (  # noqa: E402
    _SCHEMA_SPECS,
    _build_schema_for_spec,
    export_all_schemas,
)

_SCHEMA_DIR = _REPO_ROOT / "schemas" / "0.1"

_METADATA_KEYS = {"$schema", "$id", "title", "description"}


def _strip_metadata(schema: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in schema.items() if k not in _METADATA_KEYS}


_ARTIFACT_TABLE = [
    (
        "packet.schema.json",
        Packet,
        build_packet,
    ),
    (
        "completion-report.schema.json",
        CompletionReport,
        build_completion_report,
    ),
    (
        "certification-manifest.schema.json",
        CertificationManifest,
        build_certification_manifest,
    ),
    (
        "evidence-artifact.schema.json",
        EvidenceArtifact,
        build_evidence_artifact,
    ),
    (
        "observation.schema.json",
        Observation,
        build_observation,
    ),
]

_ALL_FILENAMES = ["artifact-envelope.schema.json", *[row[0] for row in _ARTIFACT_TABLE]]


class TestSchemaFilesAreValidDraft202012:
    @pytest.mark.parametrize("filename", _ALL_FILENAMES)
    def test_check_schema(self, filename: str) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        Draft202012Validator.check_schema(schema)


class TestSchemaReproducibility:
    """Regenerating every schema produces byte-identical committed output."""

    @pytest.mark.parametrize("spec", _SCHEMA_SPECS, ids=lambda s: s.filename)
    def test_generated_matches_committed(self, spec: object) -> None:
        committed = (_SCHEMA_DIR / spec.filename).read_bytes()  # type: ignore[attr-defined]
        generated = _build_schema_for_spec(spec)  # type: ignore[arg-type]
        text = json.dumps(generated, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        assert committed == text.encode("utf-8")

    def test_export_all_schemas_is_idempotent(self, tmp_path: Path) -> None:
        first = export_all_schemas(tmp_path)
        first_bytes = {p.name: p.read_bytes() for p in first}
        second = export_all_schemas(tmp_path)
        second_bytes = {p.name: p.read_bytes() for p in second}
        assert first_bytes == second_bytes

    def test_export_all_schemas_matches_repo_committed_files(self, tmp_path: Path) -> None:
        exported = export_all_schemas(tmp_path)
        for path in exported:
            committed = (_SCHEMA_DIR / path.name).read_bytes()
            assert committed == path.read_bytes(), f"{path.name} differs from committed schema"


class TestExportedSchemaDiffersOnlyByMetadataAndOrdering:
    @pytest.mark.parametrize("spec", _SCHEMA_SPECS, ids=lambda s: s.filename)
    def test_business_constraints_match_raw_model_schema(self, spec: object) -> None:
        raw = spec.model.model_json_schema(mode="validation")  # type: ignore[attr-defined]
        exported = _build_schema_for_spec(spec)  # type: ignore[arg-type]

        raw_stripped = _strip_metadata(cast(dict[str, Any], raw))
        exported_stripped = _strip_metadata(cast(dict[str, Any], exported))

        # Re-serialize both with identical (sorted) key ordering so that only
        # the four approved metadata keys and presentation order can differ.
        raw_norm = json.dumps(raw_stripped, sort_keys=True)
        exported_norm = json.dumps(exported_stripped, sort_keys=True)
        assert raw_norm == exported_norm

    @pytest.mark.parametrize("spec", _SCHEMA_SPECS, ids=lambda s: s.filename)
    def test_metadata_keys_present(self, spec: object) -> None:
        exported = _build_schema_for_spec(spec)  # type: ignore[arg-type]
        for key in _METADATA_KEYS:
            assert key in exported


class TestEnvelopeSchemaUnchanged:
    def test_envelope_schema_id_preserved(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "artifact-envelope.schema.json").read_text())
        assert schema["$id"] == "https://schemas.zutfen.com/zadc/0.1/artifact.schema.json"


class TestPerModelSchemaIdMatchesFilename:
    @pytest.mark.parametrize("filename,cls,_builder", _ARTIFACT_TABLE)
    def test_id_matches_filename(self, filename: str, cls: type, _builder: object) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        assert schema["$id"] == f"https://schemas.zutfen.com/zadc/0.1/{filename}"


class TestSchemaAcceptsRepresentativeValidInstance:
    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_sealed_instance_validates(self, filename: str, cls: type, builder: object) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        instance = builder()  # type: ignore[operator]
        sealed = seal_artifact(instance)
        data = json.loads(canonical_json_text(sealed))
        errors = list(validator.iter_errors(data))
        assert errors == [], f"{filename} rejected a valid instance: {errors}"

    def test_envelope_schema_accepts_sealed_packet_envelope_subset(self) -> None:
        # The envelope schema is additionalProperties: false over ONLY the
        # envelope fields, so a full Packet instance (which adds body
        # fields) is correctly rejected by the envelope schema alone.
        schema = json.loads((_SCHEMA_DIR / "artifact-envelope.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_packet())
        data = json.loads(canonical_json_text(sealed))
        errors = list(validator.iter_errors(data))
        assert errors != [], "envelope schema should reject Packet body fields as additional"


class TestSchemaRejectsRepresentativeInvalidInstances:
    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_missing_required_field_rejected(
        self, filename: str, cls: type, builder: object
    ) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(builder())  # type: ignore[operator]
        data = json.loads(canonical_json_text(sealed))
        del data["artifact_id"]
        errors = list(validator.iter_errors(data))
        assert errors != []

    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_wrong_const_rejected(self, filename: str, cls: type, builder: object) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(builder())  # type: ignore[operator]
        data = json.loads(canonical_json_text(sealed))
        data["contract_version"] = "9.9.9"
        errors = list(validator.iter_errors(data))
        assert errors != []

    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_wrong_artifact_type_enum_rejected(
        self, filename: str, cls: type, builder: object
    ) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(builder())  # type: ignore[operator]
        data = json.loads(canonical_json_text(sealed))
        data["artifact_type"] = "review_report"
        errors = list(validator.iter_errors(data))
        assert errors != []

    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_bad_global_id_rejected(self, filename: str, cls: type, builder: object) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(builder())  # type: ignore[operator]
        data = json.loads(canonical_json_text(sealed))
        data["project_id"] = "not a valid global id!!"
        errors = list(validator.iter_errors(data))
        assert errors != []

    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_bad_timestamp_rejected(self, filename: str, cls: type, builder: object) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(builder())  # type: ignore[operator]
        data = json.loads(canonical_json_text(sealed))
        data["created_at"] = "2026-07-31 12:00:00Z"
        errors = list(validator.iter_errors(data))
        assert errors != []

    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_nested_extra_property_rejected(
        self, filename: str, cls: type, builder: object
    ) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(builder())  # type: ignore[operator]
        data = json.loads(canonical_json_text(sealed))
        data["producer"] = {**data["producer"], "unexpected_field": "nope"}
        errors = list(validator.iter_errors(data))
        assert errors != []


class TestPacketSchemaRejectsNestedInvalid:
    def _schema_validator(self) -> Draft202012Validator:
        schema = json.loads((_SCHEMA_DIR / "packet.schema.json").read_text())
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def _valid_data(self) -> dict[str, Any]:
        sealed = seal_artifact(build_packet())
        return cast(dict[str, Any], json.loads(canonical_json_text(sealed)))

    def test_negative_pull_request_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data()
        data["repository"] = copy.deepcopy(data["repository"])
        data["repository"]["pull_request"] = -1
        assert list(validator.iter_errors(data)) != []

    def test_bad_mismatch_policy_enum_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data()
        data["work_start"] = copy.deepcopy(data["work_start"])
        data["work_start"]["mismatch_policy"] = "ignore"
        assert list(validator.iter_errors(data)) != []

    def test_bad_git_sha_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data()
        data["work_start"] = copy.deepcopy(data["work_start"])
        data["work_start"]["expected_sha"] = "not-a-sha"
        assert list(validator.iter_errors(data)) != []


class TestCertificationManifestSchemaRejectsNestedInvalid:
    def test_bad_lane_conclusion_enum_rejected(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "certification-manifest.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_certification_manifest())
        data = json.loads(canonical_json_text(sealed))
        data["lanes"][0]["conclusion"] = "not-a-real-conclusion"
        assert list(validator.iter_errors(data)) != []

    def test_bad_result_enum_rejected(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "certification-manifest.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_certification_manifest())
        data = json.loads(canonical_json_text(sealed))
        data["result"] = "maybe"
        assert list(validator.iter_errors(data)) != []

    def test_pr_head_subject_missing_head_sha_rejected(self) -> None:
        """MAJOR-2: subject-kind if/then now surfaces the pr_head presence gate."""
        schema = json.loads((_SCHEMA_DIR / "certification-manifest.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_certification_manifest())
        data = json.loads(canonical_json_text(sealed))
        assert data["subject"]["subject_kind"] == "pr_head"
        del data["subject"]["head_sha"]
        assert list(validator.iter_errors(data)) != []

    def test_synthetic_merge_subject_missing_supporting_shas_rejected(self) -> None:
        """MAJOR-2: subject-kind if/then now surfaces the synthetic_merge presence gate."""
        schema = json.loads((_SCHEMA_DIR / "certification-manifest.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sha = "c" * 40
        manifest = build_certification_manifest(
            subject={
                "repository_id": "github:Zutfen-LLC/zadc",
                "subject_kind": "synthetic_merge",
                "subject_sha": sha,
                "base_sha": "a" * 40,
                "head_sha": "b" * 40,
                "synthetic_merge_sha": sha,
            }
        )
        sealed = seal_artifact(manifest)
        data = json.loads(canonical_json_text(sealed))
        del data["subject"]["base_sha"]
        del data["subject"]["head_sha"]
        del data["subject"]["synthetic_merge_sha"]
        assert list(validator.iter_errors(data)) != []

    def test_result_pass_with_failing_mandatory_lane_rejected(self) -> None:
        """MAJOR-2: result/lane if/then now surfaces the mandatory-lane pass gate."""
        schema = json.loads((_SCHEMA_DIR / "certification-manifest.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_certification_manifest())
        data = json.loads(canonical_json_text(sealed))
        # Bypass the runtime model_validator by mutating the raw dict directly,
        # proving the *schema itself* — not just the model — rejects this.
        data["lanes"][0]["classification"] = "mandatory"
        data["lanes"][0]["conclusion"] = "fail"
        data["result"] = "pass"
        assert list(validator.iter_errors(data)) != []

    def test_result_pass_with_failing_advisory_lane_still_accepted(self) -> None:
        """The if/then gate is scoped to mandatory lanes only, per the model."""
        schema = json.loads((_SCHEMA_DIR / "certification-manifest.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_certification_manifest())
        data = json.loads(canonical_json_text(sealed))
        data["lanes"][0]["classification"] = "advisory"
        data["lanes"][0]["conclusion"] = "fail"
        data["result"] = "pass"
        assert list(validator.iter_errors(data)) == []


class TestEvidenceArtifactSchemaRejectsNestedInvalid:
    def test_negative_size_bytes_rejected(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "evidence-artifact.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_evidence_artifact())
        data = json.loads(canonical_json_text(sealed))
        data["size_bytes"] = -5
        assert list(validator.iter_errors(data)) != []

    def test_bad_availability_enum_rejected(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "evidence-artifact.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_evidence_artifact())
        data = json.loads(canonical_json_text(sealed))
        data["availability"] = "sometimes"
        assert list(validator.iter_errors(data)) != []

    def test_pr_head_subject_missing_head_sha_rejected(self) -> None:
        """MAJOR-2: the shared ExactSubject if/then also applies via
        evidence-artifact.schema.json."""
        schema = json.loads((_SCHEMA_DIR / "evidence-artifact.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        artifact = build_evidence_artifact(
            subject={
                "repository_id": "github:Zutfen-LLC/zadc",
                "subject_kind": "pr_head",
                "subject_sha": "b" * 40,
                "head_sha": "b" * 40,
            }
        )
        sealed = seal_artifact(artifact)
        data = json.loads(canonical_json_text(sealed))
        del data["subject"]["head_sha"]
        assert list(validator.iter_errors(data)) != []


class TestReconciliationSchemaRejectsNestedInvalid:
    def test_empty_intervening_commits_rejected(self) -> None:
        """MAJOR-1: minItems: 1 is now model-owned on Reconciliation.intervening_commits."""
        schema = json.loads((_SCHEMA_DIR / "completion-report.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sha_c = "c" * 40
        report = build_completion_report(
            work_start={
                "expected_sha": "a" * 40,
                "actual_sha": "b" * 40,
                "match": False,
                "reconciliation": {
                    "intervening_commits": [
                        {"sha": sha_c, "disposition": "evidence-only", "rationale": "ci log"}
                    ]
                },
            }
        )
        sealed = seal_artifact(report)
        data = json.loads(canonical_json_text(sealed))
        data["work_start"]["reconciliation"]["intervening_commits"] = []
        assert list(validator.iter_errors(data)) != []

    def test_intervening_commits_schema_declares_min_items(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "completion-report.schema.json").read_text())
        reconciliation_def = schema["$defs"]["Reconciliation"]
        commits_schema = reconciliation_def["properties"]["intervening_commits"]
        assert commits_schema["minItems"] == 1
        assert commits_schema["uniqueItems"] is True


class TestObservationSchemaRejectsNestedInvalid:
    def test_negative_freshness_seconds_rejected(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "observation.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_observation())
        data = json.loads(canonical_json_text(sealed))
        data["freshness_seconds"] = 0
        assert list(validator.iter_errors(data)) != []

    def test_bad_epistemic_status_enum_rejected(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "observation.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_observation())
        data = json.loads(canonical_json_text(sealed))
        data["epistemic_status"] = "MAYBE_TRUE"
        assert list(validator.iter_errors(data)) != []
