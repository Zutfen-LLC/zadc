"""A2B2: schema export proofs for WorkflowBundle and the global ZadcArtifact union.

Mirrors the A2B1 schema-export proof shape (see
``tests/test_a2b1_schema_export.py``): each committed schema is a valid
Draft 2020-12 schema; each accepts a representative valid sealed artifact
and rejects representative invalid variants; regeneration is byte-identical;
and the exported schema differs from the raw model/adapter schema only by
approved document metadata and key ordering. It additionally proves the
union schema independently accepts all eight variants, rejects bad
discriminators, that the ``uniqueItems`` scalar/whole-object signals are
schema-owned (not merely runtime-owned) for WorkflowBundle's collections,
and (MAJOR-3) that the supersession-requires-parent-lineage ``minItems: 1``
gate is schema-owned and independently enforced by a raw Draft 2020-12
validator, bypassing the runtime model entirely.
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
from tests.a2b1_factories import build_decision_record, build_review_report
from tests.a2b2_factories import DIGEST_C, build_minimal_workflow_bundle, build_workflow_bundle
from zadc import Provenance
from zadc.canonical import canonical_json_text
from zadc.digests import seal_artifact
from zadc.models.shared import ArtifactReference

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_schemas import (  # noqa: E402
    _SCHEMA_SPECS,
    _build_schema_for_spec,
    _raw_json_schema,
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


def _valid_bundle_data(**overrides: object) -> dict[str, Any]:
    sealed = seal_artifact(build_workflow_bundle(**overrides))
    return cast(dict[str, Any], json.loads(canonical_json_text(sealed)))


_UNION_VARIANT_TABLE = [
    ("packet", build_packet),
    ("completion_report", build_completion_report),
    ("certification_manifest", build_certification_manifest),
    ("evidence_artifact", build_evidence_artifact),
    ("observation", build_observation),
    ("review_report", build_review_report),
    ("decision_record", build_decision_record),
    ("workflow_bundle", build_workflow_bundle),
]


class TestSchemaFilesAreValidDraft202012:
    @pytest.mark.parametrize(
        "filename", ["workflow-bundle.schema.json", "zadc-artifact.schema.json"]
    )
    def test_check_schema(self, filename: str) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        Draft202012Validator.check_schema(schema)


class TestSchemaReproducibility:
    @pytest.mark.parametrize(
        "filename", ["workflow-bundle.schema.json", "zadc-artifact.schema.json"]
    )
    def test_generated_matches_committed(self, filename: str) -> None:
        spec = _spec_for(filename)
        committed = (_SCHEMA_DIR / filename).read_bytes()
        generated = _build_schema_for_spec(spec)  # type: ignore[arg-type]
        text = json.dumps(generated, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        assert committed == text.encode("utf-8")


class TestExportedSchemaDiffersOnlyByMetadataAndOrdering:
    @pytest.mark.parametrize(
        "filename", ["workflow-bundle.schema.json", "zadc-artifact.schema.json"]
    )
    def test_business_constraints_match_raw_source_schema(self, filename: str) -> None:
        spec = _spec_for(filename)
        raw = _raw_json_schema(spec)  # type: ignore[arg-type]
        exported = _build_schema_for_spec(spec)  # type: ignore[arg-type]

        raw_norm = json.dumps(_strip_metadata(raw), sort_keys=True)
        exported_norm = json.dumps(_strip_metadata(cast(dict[str, Any], exported)), sort_keys=True)
        assert raw_norm == exported_norm

    @pytest.mark.parametrize(
        "filename", ["workflow-bundle.schema.json", "zadc-artifact.schema.json"]
    )
    def test_id_matches_filename(self, filename: str) -> None:
        schema = json.loads((_SCHEMA_DIR / filename).read_text())
        assert schema["$id"] == f"https://schemas.zutfen.com/zadc/0.1/{filename}"


class TestWorkflowBundleSchemaAcceptsValidInstances:
    def _schema_validator(self) -> Draft202012Validator:
        schema = json.loads((_SCHEMA_DIR / "workflow-bundle.schema.json").read_text())
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def test_populated_bundle_accepted(self) -> None:
        validator = self._schema_validator()
        data = _valid_bundle_data()
        assert list(validator.iter_errors(data)) == []

    def test_minimal_bundle_accepted(self) -> None:
        validator = self._schema_validator()
        sealed = seal_artifact(build_minimal_workflow_bundle())
        data = json.loads(canonical_json_text(sealed))
        assert list(validator.iter_errors(data)) == []


class TestWorkflowBundleSchemaRejectsInvalidInstances:
    def _schema_validator(self) -> Draft202012Validator:
        schema = json.loads((_SCHEMA_DIR / "workflow-bundle.schema.json").read_text())
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def test_missing_required_field_rejected(self) -> None:
        validator = self._schema_validator()
        data = _valid_bundle_data()
        del data["bundle_id"]
        assert list(validator.iter_errors(data)) != []

    def test_wrong_const_rejected(self) -> None:
        validator = self._schema_validator()
        data = _valid_bundle_data()
        data["contract_version"] = "9.9.9"
        assert list(validator.iter_errors(data)) != []

    def test_wrong_artifact_type_enum_rejected(self) -> None:
        validator = self._schema_validator()
        data = _valid_bundle_data()
        data["artifact_type"] = "packet"
        assert list(validator.iter_errors(data)) != []

    def test_bad_global_id_rejected(self) -> None:
        validator = self._schema_validator()
        data = _valid_bundle_data()
        data["project_id"] = "not a valid global id!!"
        assert list(validator.iter_errors(data)) != []

    def test_bad_timestamp_rejected(self) -> None:
        validator = self._schema_validator()
        data = _valid_bundle_data()
        data["created_at"] = "2026-07-31 12:00:00Z"
        assert list(validator.iter_errors(data)) != []

    def test_nested_extra_property_rejected(self) -> None:
        validator = self._schema_validator()
        data = _valid_bundle_data()
        data["producer"] = {**data["producer"], "unexpected_field": "nope"}
        assert list(validator.iter_errors(data)) != []

    def test_derived_state_extra_property_rejected(self) -> None:
        validator = self._schema_validator()
        data = _valid_bundle_data()
        data["derived_state"] = {**data["derived_state"], "unexpected_field": "nope"}
        assert list(validator.iter_errors(data)) != []


class TestWorkflowBundleSchemaUniqueItemsIndependentlyProven:
    """MAJOR-2 style: uniqueItems is schema-owned, proven by mutating the raw
    dict directly (bypassing the runtime model_validator entirely)."""

    def _schema_validator(self) -> Draft202012Validator:
        schema = json.loads((_SCHEMA_DIR / "workflow-bundle.schema.json").read_text())
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def test_next_admissible_actions_scalar_duplicate_rejected(self) -> None:
        validator = self._schema_validator()
        data = _valid_bundle_data()
        data["derived_state"] = copy.deepcopy(data["derived_state"])
        data["derived_state"]["next_admissible_actions"] = ["submit_review", "submit_review"]
        assert list(validator.iter_errors(data)) != []

    def test_completion_report_refs_whole_object_duplicate_rejected(self) -> None:
        validator = self._schema_validator()
        data = _valid_bundle_data()
        ref = data["completion_report_refs"][0]
        data["completion_report_refs"] = [ref, dict(ref)]
        assert list(validator.iter_errors(data)) != []

    def test_input_artifact_refs_whole_object_duplicate_rejected(self) -> None:
        validator = self._schema_validator()
        data = _valid_bundle_data()
        data["derived_state"] = copy.deepcopy(data["derived_state"])
        ref = data["derived_state"]["input_artifact_refs"][0]
        data["derived_state"]["input_artifact_refs"] = [ref, dict(ref)]
        assert list(validator.iter_errors(data)) != []

    def test_next_admissible_actions_distinct_values_still_accepted(self) -> None:
        """Sanity: the gate only fires on duplicates."""
        validator = self._schema_validator()
        data = _valid_bundle_data()
        assert list(validator.iter_errors(data)) == []


class TestWorkflowBundleSchemaAllOfScopedToSupersessionGate:
    """MAJOR-3 corrected: most WorkflowBundle cross-collection/cross-object
    invariants (self-reference, digest consistency, top-level exclusivity,
    derived-state membership, policy equality, exact supersession-parent
    *membership*) have no standard JSON Schema vocabulary and remain
    runtime-only. But one necessary portion of the supersession invariant —
    a non-null ``supersedes_bundle_ref`` requires a non-empty
    ``provenance.parent_artifact_ids`` — *is* schema-expressible via a single
    ``if``/``then`` block, and the WorkflowBundle schema now carries exactly
    that one top-level ``allOf`` gate (not a whole business-constraint
    block covering every invariant, and not none at all)."""

    def test_top_level_allof_present(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "workflow-bundle.schema.json").read_text())
        assert "allOf" in schema

    def test_allof_has_exactly_one_gate(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "workflow-bundle.schema.json").read_text())
        assert len(schema["allOf"]) == 1

    def test_gate_is_the_supersession_parent_lineage_gate(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "workflow-bundle.schema.json").read_text())
        gate = schema["allOf"][0]
        assert "supersedes_bundle_ref" in gate["if"]["properties"]
        assert gate["then"]["properties"]["provenance"]["properties"]["parent_artifact_ids"] == {
            "minItems": 1
        }


class TestWorkflowBundleSchemaSupersessionRequiresParentLineage:
    """MAJOR-3: the supersession-requires-parent-lineage gate is independently
    proven by a raw Draft 2020-12 validator against mutated dicts, bypassing
    ``WorkflowBundle``'s runtime ``model_validator`` entirely — mirroring
    ``TestWorkflowBundleSchemaUniqueItemsIndependentlyProven`` above."""

    def _schema_validator(self) -> Draft202012Validator:
        schema = json.loads((_SCHEMA_DIR / "workflow-bundle.schema.json").read_text())
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def _superseding_bundle_data(self) -> dict[str, Any]:
        other_id = "urn:uuid:00000000-0000-0000-0000-000000000800"
        other_ref = ArtifactReference(artifact_id=other_id, content_digest=DIGEST_C)
        bundle = build_workflow_bundle(
            supersedes_bundle_ref=other_ref,
            provenance=Provenance(parent_artifact_ids=(other_id,)),
        )
        sealed = seal_artifact(bundle)
        return cast(dict[str, Any], json.loads(canonical_json_text(sealed)))

    def test_supersession_with_empty_parent_ids_rejected(self) -> None:
        validator = self._schema_validator()
        data = self._superseding_bundle_data()
        data["provenance"] = dict(data["provenance"])
        data["provenance"]["parent_artifact_ids"] = []
        assert list(validator.iter_errors(data)) != []

    def test_supersession_with_nonempty_parent_ids_accepted(self) -> None:
        validator = self._schema_validator()
        data = self._superseding_bundle_data()
        assert list(validator.iter_errors(data)) == []

    def test_no_supersession_with_empty_parent_ids_still_accepted(self) -> None:
        """Sanity: the gate only fires when supersedes_bundle_ref is non-null."""
        validator = self._schema_validator()
        data = _valid_bundle_data()
        assert data["supersedes_bundle_ref"] is None
        assert data["provenance"]["parent_artifact_ids"] == []
        assert list(validator.iter_errors(data)) == []


class TestZadcArtifactSchemaDiscriminator:
    def test_discriminator_covers_all_eight_variants(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "zadc-artifact.schema.json").read_text())
        mapping = schema["discriminator"]["mapping"]
        assert schema["discriminator"]["propertyName"] == "artifact_type"
        assert set(mapping.keys()) == {name for name, _ in _UNION_VARIANT_TABLE}
        for ref in mapping.values():
            assert ref.startswith("#/$defs/")

    def test_oneof_has_eight_entries(self) -> None:
        schema = json.loads((_SCHEMA_DIR / "zadc-artifact.schema.json").read_text())
        assert len(schema["oneOf"]) == 8


class TestZadcArtifactSchemaAcceptsAllVariants:
    def _schema_validator(self) -> Draft202012Validator:
        schema = json.loads((_SCHEMA_DIR / "zadc-artifact.schema.json").read_text())
        return Draft202012Validator(schema, format_checker=FormatChecker())

    @pytest.mark.parametrize("artifact_type,builder", _UNION_VARIANT_TABLE)
    def test_sealed_variant_accepted(self, artifact_type: str, builder: object) -> None:
        validator = self._schema_validator()
        sealed = seal_artifact(builder())  # type: ignore[operator]
        data = json.loads(canonical_json_text(sealed))
        assert data["artifact_type"] == artifact_type
        errors = list(validator.iter_errors(data))
        assert errors == [], f"{artifact_type} rejected: {errors}"


class TestZadcArtifactSchemaRejectsBadDiscriminators:
    def _schema_validator(self) -> Draft202012Validator:
        schema = json.loads((_SCHEMA_DIR / "zadc-artifact.schema.json").read_text())
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def test_unknown_discriminator_rejected(self) -> None:
        validator = self._schema_validator()
        sealed = seal_artifact(build_packet())
        data = json.loads(canonical_json_text(sealed))
        data["artifact_type"] = "not_a_real_type"
        assert list(validator.iter_errors(data)) != []

    def test_missing_discriminator_rejected(self) -> None:
        validator = self._schema_validator()
        sealed = seal_artifact(build_packet())
        data = json.loads(canonical_json_text(sealed))
        del data["artifact_type"]
        assert list(validator.iter_errors(data)) != []

    def test_null_discriminator_rejected(self) -> None:
        validator = self._schema_validator()
        sealed = seal_artifact(build_packet())
        data = json.loads(canonical_json_text(sealed))
        data["artifact_type"] = None
        assert list(validator.iter_errors(data)) != []

    def test_body_discriminator_mismatch_rejected(self) -> None:
        validator = self._schema_validator()
        sealed = seal_artifact(build_workflow_bundle())
        data = json.loads(canonical_json_text(sealed))
        data["artifact_type"] = "packet"
        assert list(validator.iter_errors(data)) != []

    def test_nested_extra_property_rejected(self) -> None:
        validator = self._schema_validator()
        sealed = seal_artifact(build_packet())
        data = json.loads(canonical_json_text(sealed))
        data["producer"] = {**data["producer"], "unexpected_field": "nope"}
        assert list(validator.iter_errors(data)) != []

    def test_cross_variant_field_rejected(self) -> None:
        validator = self._schema_validator()
        sealed = seal_artifact(build_packet())
        data = json.loads(canonical_json_text(sealed))
        data["bundle_id"] = "urn:uuid:00000000-0000-0000-0000-000000000999"
        assert list(validator.iter_errors(data)) != []
