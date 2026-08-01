"""A2B1: schema export proofs for ReviewReport and DecisionRecord.

Mirrors the A2A schema-export proof shape (see
``tests/test_a2a_schema_export.py``) without duplicating its generic
parametrized suite — this module adds the two new specs to the same
data-driven exporter and proves: each committed schema is a valid Draft
2020-12 schema; each accepts a representative valid sealed artifact and
rejects representative invalid variants; regeneration is byte-identical;
and the schema differs from the raw model schema only by approved document
metadata and key ordering. It also independently proves the
decision/finding-specific conditional gates — missing and explicit-null
cases separately — directly against the generated schema, not just the
Python model.
"""

import copy
import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]
from pydantic import BaseModel

from tests.a2b1_factories import DIGEST_C, build_decision_record, build_review_report
from zadc import ProducerIdentity
from zadc.canonical import canonical_json_text
from zadc.digests import seal_artifact
from zadc.models.decision_record import DecisionRecord
from zadc.models.review_report import ReviewerIdentity, ReviewReport

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_schemas import (  # noqa: E402
    _SCHEMA_SPECS,
    _build_schema_for_spec,
)

_SCHEMA_DIR = _REPO_ROOT / "schemas" / "0.1"
_METADATA_KEYS = {"$schema", "$id", "title", "description"}


def _strip_metadata(schema: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in schema.items() if k not in _METADATA_KEYS}


def _spec_for(filename: str) -> object:
    for spec in _SCHEMA_SPECS:
        if spec.filename == filename:
            return spec
    raise AssertionError(f"no schema spec named {filename!r}")


_ARTIFACT_TABLE = [
    ("review-report.schema.json", ReviewReport, build_review_report),
    ("decision-record.schema.json", DecisionRecord, build_decision_record),
]


class TestSchemaFilesAreValidDraft202012:
    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_check_schema(self, filename: str, cls: type[BaseModel], builder: object) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        Draft202012Validator.check_schema(schema)


class TestSchemaReproducibility:
    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_generated_matches_committed(
        self, filename: str, cls: type[BaseModel], builder: object
    ) -> None:
        spec = _spec_for(filename)
        committed = (_SCHEMA_DIR / filename).read_bytes()
        generated = _build_schema_for_spec(spec)  # type: ignore[arg-type]
        text = json.dumps(generated, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        assert committed == text.encode("utf-8")


class TestExportedSchemaDiffersOnlyByMetadataAndOrdering:
    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_business_constraints_match_raw_model_schema(
        self, filename: str, cls: type[BaseModel], builder: object
    ) -> None:
        spec = _spec_for(filename)
        raw = cls.model_json_schema(mode="validation")
        exported = _build_schema_for_spec(spec)  # type: ignore[arg-type]

        raw_norm = json.dumps(_strip_metadata(raw), sort_keys=True)
        exported_norm = json.dumps(_strip_metadata(cast(dict[str, Any], exported)), sort_keys=True)
        assert raw_norm == exported_norm

    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_id_matches_filename(
        self, filename: str, cls: type[BaseModel], builder: object
    ) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        assert schema["$id"] == f"https://schemas.zutfen.com/zadc/0.1/{filename}"


class TestSchemaAcceptsRepresentativeValidInstance:
    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_sealed_instance_validates(
        self, filename: str, cls: type[BaseModel], builder: object
    ) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        instance = builder()  # type: ignore[operator]
        sealed = seal_artifact(instance)
        data = json.loads(canonical_json_text(sealed))
        errors = list(validator.iter_errors(data))
        assert errors == [], f"{filename} rejected a valid instance: {errors}"


class TestSchemaRejectsRepresentativeInvalidInstances:
    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_missing_required_field_rejected(
        self, filename: str, cls: type[BaseModel], builder: object
    ) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(builder())  # type: ignore[operator]
        data = json.loads(canonical_json_text(sealed))
        del data["artifact_id"]
        assert list(validator.iter_errors(data)) != []

    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_wrong_const_rejected(
        self, filename: str, cls: type[BaseModel], builder: object
    ) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(builder())  # type: ignore[operator]
        data = json.loads(canonical_json_text(sealed))
        data["contract_version"] = "9.9.9"
        assert list(validator.iter_errors(data)) != []

    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_wrong_artifact_type_enum_rejected(
        self, filename: str, cls: type[BaseModel], builder: object
    ) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(builder())  # type: ignore[operator]
        data = json.loads(canonical_json_text(sealed))
        data["artifact_type"] = "packet"
        assert list(validator.iter_errors(data)) != []

    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_bad_global_id_rejected(
        self, filename: str, cls: type[BaseModel], builder: object
    ) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(builder())  # type: ignore[operator]
        data = json.loads(canonical_json_text(sealed))
        data["project_id"] = "not a valid global id!!"
        assert list(validator.iter_errors(data)) != []

    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_bad_timestamp_rejected(
        self, filename: str, cls: type[BaseModel], builder: object
    ) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(builder())  # type: ignore[operator]
        data = json.loads(canonical_json_text(sealed))
        data["created_at"] = "2026-07-31 12:00:00Z"
        assert list(validator.iter_errors(data)) != []

    @pytest.mark.parametrize("filename,cls,builder", _ARTIFACT_TABLE)
    def test_nested_extra_property_rejected(
        self, filename: str, cls: type[BaseModel], builder: object
    ) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(builder())  # type: ignore[operator]
        data = json.loads(canonical_json_text(sealed))
        data["producer"] = {**data["producer"], "unexpected_field": "nope"}
        assert list(validator.iter_errors(data)) != []


class TestReviewReportSchemaRejectsNestedInvalid:
    def _schema_validator(self) -> Draft202012Validator:
        schema = json.loads((_SCHEMA_DIR / "review-report.schema.json").read_text())
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def _valid_data(self) -> dict[str, Any]:
        sealed = seal_artifact(build_review_report())
        return cast(dict[str, Any], json.loads(canonical_json_text(sealed)))

    def test_bad_reviewer_recommendation_enum_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data()
        data["reviewer_recommendation"] = "maybe"
        assert list(validator.iter_errors(data)) != []

    def test_bad_finding_status_enum_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data()
        data["findings"][0]["status"] = "not-a-real-status"
        assert list(validator.iter_errors(data)) != []

    def test_resolved_finding_missing_resolution_refs_rejected(self) -> None:
        """Bypass the runtime model_validator by mutating the raw dict
        directly, proving the *schema itself* rejects this."""
        validator = self._schema_validator()
        data = self._valid_data()
        data["findings"][0]["status"] = "resolved"
        data["findings"][0]["resolution_refs"] = []
        assert list(validator.iter_errors(data)) != []

    def test_accepted_risk_finding_missing_resolution_refs_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data()
        data["findings"][0]["status"] = "accepted_risk"
        data["findings"][0]["resolution_refs"] = []
        assert list(validator.iter_errors(data)) != []

    def test_open_finding_with_empty_resolution_refs_still_accepted(self) -> None:
        """The gate is scoped to resolved/accepted_risk only."""
        validator = self._schema_validator()
        data = self._valid_data()
        data["findings"][0]["status"] = "open"
        data["findings"][0]["resolution_refs"] = []
        assert list(validator.iter_errors(data)) == []

    def test_file_location_with_cross_variant_field_rejected(self) -> None:
        """A ``file`` location carrying ``artifact``-only fields is
        rejected by the discriminated oneOf (each variant is
        additionalProperties: false)."""
        validator = self._schema_validator()
        data = self._valid_data()
        data["findings"][0]["location"] = {
            "location_type": "file",
            "path": "a.py",
            "artifact_id": "urn:uuid:00000000-0000-0000-0000-000000000050",
        }
        assert list(validator.iter_errors(data)) != []

    def test_unknown_location_type_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data()
        data["findings"][0]["location"] = {"location_type": "unknown", "path": "a.py"}
        assert list(validator.iter_errors(data)) != []


class TestDecisionRecordSchemaRejectsNestedInvalid:
    def _schema_validator(self) -> Draft202012Validator:
        schema = json.loads((_SCHEMA_DIR / "decision-record.schema.json").read_text())
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def _valid_data(self, **overrides: object) -> dict[str, Any]:
        sealed = seal_artifact(build_decision_record(**overrides))
        return cast(dict[str, Any], json.loads(canonical_json_text(sealed)))

    def test_bad_decision_enum_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data()
        data["decision"] = "not-a-real-decision"
        assert list(validator.iter_errors(data)) != []

    def test_accept_risk_with_empty_accepted_risks_rejected(self) -> None:
        """Bypass the runtime model_validator by mutating the raw dict
        directly, proving the *schema itself* enforces the minItems gate."""
        validator = self._schema_validator()
        data = self._valid_data()
        data["decision"] = "accept_risk"
        data["accepted_risks"] = []
        assert list(validator.iter_errors(data)) != []

    def test_non_accept_risk_with_nonempty_accepted_risks_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data(
            decision="accept_risk",
            accepted_risks=[
                {"finding_id": "F-1", "rationale": "x", "scope": "y", "expires_at": None}
            ],
        )
        data["decision"] = "approve_for_merge"
        assert list(validator.iter_errors(data)) != []

    def test_supersede_missing_supersedes_decision_ref_key_rejected(self) -> None:
        """Missing-key case, proven independently of the explicit-null case."""
        validator = self._schema_validator()
        data = self._valid_data(
            decision="supersede",
            supersedes_decision_ref={
                "artifact_id": "urn:uuid:00000000-0000-0000-0000-000000000777",
                "content_digest": DIGEST_C,
            },
        )
        del data["supersedes_decision_ref"]
        assert list(validator.iter_errors(data)) != []

    def test_supersede_explicit_null_supersedes_decision_ref_rejected(self) -> None:
        """Explicit-null case, proven independently of the missing-key case."""
        validator = self._schema_validator()
        data = self._valid_data(
            decision="supersede",
            supersedes_decision_ref={
                "artifact_id": "urn:uuid:00000000-0000-0000-0000-000000000777",
                "content_digest": DIGEST_C,
            },
        )
        data["supersedes_decision_ref"] = None
        assert list(validator.iter_errors(data)) != []

    def test_non_supersede_nonnull_supersedes_decision_ref_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data(
            decision="supersede",
            supersedes_decision_ref={
                "artifact_id": "urn:uuid:00000000-0000-0000-0000-000000000777",
                "content_digest": DIGEST_C,
            },
        )
        data["decision"] = "approve_for_merge"
        assert list(validator.iter_errors(data)) != []

    def test_non_supersede_null_supersedes_decision_ref_still_accepted(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data()
        assert data["decision"] == "approve_for_merge"
        assert data["supersedes_decision_ref"] is None
        assert list(validator.iter_errors(data)) == []

    def test_accepted_risk_negative_via_deepcopy(self) -> None:
        """Sanity: deep-copying nested dicts before mutation matches the
        established A2A schema-test pattern (see TestPacketSchemaRejectsNestedInvalid)."""
        validator = self._schema_validator()
        data = self._valid_data()
        data["subject"] = copy.deepcopy(data["subject"])
        data["subject"]["pull_request"] = -1
        assert list(validator.iter_errors(data)) != []


class TestReviewReportSchemaEnforcesReviewerProducerActorTypeMatch:
    """MAJOR-1: the reviewer/producer actor-type match is schema-owned, not
    just runtime-owned. Bypass the runtime model_validator by mutating the
    raw dict directly, proving the *schema itself* rejects the mismatch."""

    def _schema_validator(self) -> Draft202012Validator:
        schema = json.loads((_SCHEMA_DIR / "review-report.schema.json").read_text())
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def test_human_reviewer_with_agent_producer_rejected(self) -> None:
        validator = self._schema_validator()
        sealed = seal_artifact(build_review_report())
        data = json.loads(canonical_json_text(sealed))
        assert data["reviewer"]["actor_type"] == "human"
        data["producer"] = {**data["producer"], "actor_type": "agent"}
        assert list(validator.iter_errors(data)) != []

    def test_agent_reviewer_with_human_producer_rejected(self) -> None:
        validator = self._schema_validator()
        agent_id = "zutfen:agent:claude"
        review = build_review_report(
            producer=ProducerIdentity(actor_type="agent", actor_id=agent_id),
            reviewer=ReviewerIdentity(actor_type="agent", actor_id=agent_id),
        )
        sealed = seal_artifact(review)
        data = json.loads(canonical_json_text(sealed))
        assert data["reviewer"]["actor_type"] == "agent"
        data["producer"] = {**data["producer"], "actor_type": "human"}
        assert list(validator.iter_errors(data)) != []

    def test_agent_reviewer_with_agent_producer_accepted(self) -> None:
        """Sanity: the matching agent/agent combination the mismatch tests
        are compared against is itself schema-valid."""
        validator = self._schema_validator()
        agent_id = "zutfen:agent:claude"
        review = build_review_report(
            producer=ProducerIdentity(actor_type="agent", actor_id=agent_id),
            reviewer=ReviewerIdentity(actor_type="agent", actor_id=agent_id),
        )
        sealed = seal_artifact(review)
        data = json.loads(canonical_json_text(sealed))
        assert list(validator.iter_errors(data)) == []


class TestDecisionRecordSchemaEnforcesHumanProducer:
    """MAJOR-1: DecisionRecord.producer.actor_type == 'human' is
    schema-owned. Bypass the runtime model_validator by mutating the raw
    dict directly, proving the *schema itself* rejects a non-human
    producer."""

    def test_non_human_producer_rejected(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "decision-record.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_decision_record())
        data = json.loads(canonical_json_text(sealed))
        assert data["producer"]["actor_type"] == "human"
        data["producer"] = {**data["producer"], "actor_type": "agent"}
        assert list(validator.iter_errors(data)) != []


class TestLineRangePresenceGateSchemaOwned:
    """MAJOR-2: ``end_line`` present-and-non-null requires ``start_line``
    present-and-non-null, independently proven for both ReviewedFile (via
    ``inputs_reviewed.files[]``) and FileFindingLocation (via
    ``findings[].location``), and for the omitted vs. explicit-null cases
    of ``start_line`` separately."""

    def _schema_validator(self) -> Draft202012Validator:
        schema = json.loads((_SCHEMA_DIR / "review-report.schema.json").read_text())
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def _valid_data(self) -> dict[str, Any]:
        sealed = seal_artifact(build_review_report())
        return cast(dict[str, Any], json.loads(canonical_json_text(sealed)))

    def test_reviewed_file_end_line_with_omitted_start_line_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data()
        data["inputs_reviewed"] = copy.deepcopy(data["inputs_reviewed"])
        del data["inputs_reviewed"]["files"][0]["start_line"]
        data["inputs_reviewed"]["files"][0]["end_line"] = 5
        assert list(validator.iter_errors(data)) != []

    def test_reviewed_file_end_line_with_null_start_line_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data()
        data["inputs_reviewed"] = copy.deepcopy(data["inputs_reviewed"])
        data["inputs_reviewed"]["files"][0]["start_line"] = None
        data["inputs_reviewed"]["files"][0]["end_line"] = 5
        assert list(validator.iter_errors(data)) != []

    def test_file_finding_location_end_line_with_omitted_start_line_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data()
        data["findings"][0] = copy.deepcopy(data["findings"][0])
        location = {"location_type": "file", "path": "a.py", "end_line": 5}
        data["findings"][0]["location"] = location
        assert list(validator.iter_errors(data)) != []

    def test_file_finding_location_end_line_with_null_start_line_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._valid_data()
        data["findings"][0] = copy.deepcopy(data["findings"][0])
        location = {"location_type": "file", "path": "a.py", "start_line": None, "end_line": 5}
        data["findings"][0]["location"] = location
        assert list(validator.iter_errors(data)) != []

    def test_end_line_with_present_start_line_still_accepted(self) -> None:
        """The gate only fires when end_line is present and non-null."""
        validator = self._schema_validator()
        data = self._valid_data()
        data["inputs_reviewed"] = copy.deepcopy(data["inputs_reviewed"])
        data["inputs_reviewed"]["files"][0]["start_line"] = 1
        data["inputs_reviewed"]["files"][0]["end_line"] = 5
        assert list(validator.iter_errors(data)) == []


class TestScalarIdArrayUniqueItemsSchemaOwned:
    """MAJOR-2: scalar GlobalId array fields declare ``uniqueItems: true``
    and independently reject duplicates at the schema level, for all three
    named fields."""

    def test_review_subject_certification_manifest_ids_duplicate_rejected(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "review-report.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_review_report())
        data = json.loads(canonical_json_text(sealed))
        manifest_id = data["subject"]["certification_manifest_ids"][0]
        data["subject"] = copy.deepcopy(data["subject"])
        data["subject"]["certification_manifest_ids"] = [manifest_id, manifest_id]
        assert list(validator.iter_errors(data)) != []

    def test_decision_subject_review_report_ids_duplicate_rejected(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "decision-record.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_decision_record())
        data = json.loads(canonical_json_text(sealed))
        review_id = data["subject"]["review_report_ids"][0]
        data["subject"] = copy.deepcopy(data["subject"])
        data["subject"]["review_report_ids"] = [review_id, review_id]
        assert list(validator.iter_errors(data)) != []

    def test_decision_subject_certification_manifest_ids_duplicate_rejected(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "decision-record.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        sealed = seal_artifact(build_decision_record())
        data = json.loads(canonical_json_text(sealed))
        manifest_id = data["subject"]["certification_manifest_ids"][0]
        data["subject"] = copy.deepcopy(data["subject"])
        data["subject"]["certification_manifest_ids"] = [manifest_id, manifest_id]
        assert list(validator.iter_errors(data)) != []
