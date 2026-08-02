"""A3A: schema export proofs for the RenderedView projection record.

Mirrors the A2B2 schema-export proof shape (see
``tests/test_a2b2_schema_export.py``): the committed schema is a valid
Draft 2020-12 schema; it accepts a representative valid rendered view and
rejects representative invalid variants; regeneration is byte-identical;
and the exported schema differs from the raw model schema only by approved
document metadata and key ordering. It additionally proves the
``rendered_at >= source_created_at`` chronology invariant is runtime-only,
that RenderedView was NOT added to ``zadc-artifact.schema.json``, and that
all ten prior committed schemas regenerate byte-identically alongside the
new eleventh schema.
"""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from tests.a2a_factories import build_packet
from zadc import seal_artifact
from zadc.canonical import canonical_json_text
from zadc.rendering import (
    RENDERED_VIEW_SCHEMA_ID,
    render_artifact,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.export_schemas import (  # noqa: E402
    _SCHEMA_SPECS,
    _build_schema_for_spec,
    _raw_json_schema,
)

_SCHEMA_DIR = _REPO_ROOT / "schemas" / "0.1"
_RENDERED_VIEW_FILE = "rendered-view.schema.json"
_ZADC_ARTIFACT_FILE = "zadc-artifact.schema.json"
_METADATA_KEYS = {"$schema", "$id", "title", "description"}


def _strip_metadata(schema: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in schema.items() if k not in _METADATA_KEYS}


def _spec_for(filename: str) -> Any:
    for spec in _SCHEMA_SPECS:
        if spec.filename == filename:
            return spec
    raise AssertionError(f"no schema spec named {filename!r}")


def _valid_view_data() -> dict[str, Any]:
    sealed = seal_artifact(build_packet())
    view = render_artifact(
        sealed, rendered_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC), consumer="ci"
    )
    return cast(dict[str, Any], json.loads(canonical_json_text(view)))


class TestRenderedViewSchemaIsValid:
    def test_check_schema(self) -> None:
        schema = json.loads((_SCHEMA_DIR / _RENDERED_VIEW_FILE).read_text())
        Draft202012Validator.check_schema(schema)

    def test_schema_id(self) -> None:
        schema = json.loads((_SCHEMA_DIR / _RENDERED_VIEW_FILE).read_text())
        assert schema["$id"] == RENDERED_VIEW_SCHEMA_ID

    def test_draft(self) -> None:
        schema = json.loads((_SCHEMA_DIR / _RENDERED_VIEW_FILE).read_text())
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


class TestRenderedViewSchemaReproducibility:
    def test_generated_matches_committed(self) -> None:
        spec = _spec_for(_RENDERED_VIEW_FILE)
        committed = (_SCHEMA_DIR / _RENDERED_VIEW_FILE).read_bytes()
        generated = _build_schema_for_spec(spec)
        text = json.dumps(generated, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        assert committed == text.encode("utf-8")

    def test_business_constraints_match_raw_model_schema(self) -> None:
        spec = _spec_for(_RENDERED_VIEW_FILE)
        raw = _raw_json_schema(spec)
        exported = _build_schema_for_spec(spec)
        raw_norm = json.dumps(_strip_metadata(raw), sort_keys=True)
        exported_norm = json.dumps(_strip_metadata(cast(dict[str, Any], exported)), sort_keys=True)
        assert raw_norm == exported_norm


class TestAllSchemasRegenerateByteIdentical:
    """Proof that all ten prior schemas remain unchanged, plus the new one."""

    @pytest.mark.parametrize("spec", _SCHEMA_SPECS, ids=[s.filename for s in _SCHEMA_SPECS])
    def test_committed_matches_generated(self, spec: Any) -> None:
        committed = (_SCHEMA_DIR / spec.filename).read_bytes()
        generated = _build_schema_for_spec(spec)
        text = json.dumps(generated, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        assert committed == text.encode("utf-8"), f"{spec.filename} changed"

    def test_spec_count_is_eleven(self) -> None:
        assert len(_SCHEMA_SPECS) == 11


class TestRenderedViewNotAddedToArtifactUnion:
    def test_rendered_view_absent_from_zadc_artifact_discriminator(self) -> None:
        schema = json.loads((_SCHEMA_DIR / _ZADC_ARTIFACT_FILE).read_text())
        mapping = schema["discriminator"]["mapping"]
        assert "rendered_view" not in mapping
        assert len(schema["oneOf"]) == 8


class TestRenderedViewSchemaAcceptsValid:
    def _validator(self) -> Draft202012Validator:
        schema = json.loads((_SCHEMA_DIR / _RENDERED_VIEW_FILE).read_text())
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def test_valid_view_accepted(self) -> None:
        validator = self._validator()
        assert list(validator.iter_errors(_valid_view_data())) == []

    def test_human_view_accepted(self) -> None:
        sealed = seal_artifact(build_packet())
        view = render_artifact(
            sealed, rendered_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC), consumer="human"
        )
        data = cast(dict[str, Any], json.loads(canonical_json_text(view)))
        validator = self._validator()
        assert list(validator.iter_errors(data)) == []


class TestRenderedViewSchemaRejectsInvalid:
    def _validator(self) -> Draft202012Validator:
        schema = json.loads((_SCHEMA_DIR / _RENDERED_VIEW_FILE).read_text())
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def test_missing_required_field_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        del data["content"]
        assert list(validator.iter_errors(data)) != []

    def test_wrong_schema_const_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        data["schema"] = "https://schemas.zutfen.com/zadc/0.1/artifact.schema.json"
        assert list(validator.iter_errors(data)) != []

    def test_wrong_view_version_const_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        data["view_version"] = "9.9.9"
        assert list(validator.iter_errors(data)) != []

    def test_wrong_non_authoritative_const_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        data["non_authoritative"] = False
        assert list(validator.iter_errors(data)) != []

    def test_invalid_consumer_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        data["consumer"] = "robot"
        assert list(validator.iter_errors(data)) != []

    def test_malformed_source_project_id_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        data["source_project_id"] = "not a valid global id!!"
        assert list(validator.iter_errors(data)) != []

    def test_malformed_content_digest_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        data["source_ref"]["content_digest"] = "sha256:deadbeef"
        assert list(validator.iter_errors(data)) != []

    def test_bad_rendered_at_timestamp_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        data["rendered_at"] = "2026-08-01 12:00:00Z"
        assert list(validator.iter_errors(data)) != []

    def test_bad_source_created_at_timestamp_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        data["source_created_at"] = "not-a-timestamp"
        assert list(validator.iter_errors(data)) != []

    def test_nested_extra_property_in_renderer_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        data["renderer"] = {**data["renderer"], "extra": "nope"}
        assert list(validator.iter_errors(data)) != []

    def test_nested_extra_property_in_source_ref_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        data["source_ref"] = {**data["source_ref"], "extra": "nope"}
        assert list(validator.iter_errors(data)) != []

    def test_top_level_extra_property_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        data["unexpected"] = True
        assert list(validator.iter_errors(data)) != []

    def test_empty_content_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        data["content"] = ""
        assert list(validator.iter_errors(data)) != []

    def test_invalid_source_artifact_type_rejected(self) -> None:
        validator = self._validator()
        data = _valid_view_data()
        data["source_artifact_type"] = "rendered_view"
        assert list(validator.iter_errors(data)) != []


class TestChronologyIsRuntimeOnly:
    """The rendered_at >= source_created_at invariant has no JSON Schema
    vocabulary; the schema alone must accept a chronologically-invalid view
    (with otherwise valid timestamps), proving the gate is runtime-only."""

    def test_schema_accepts_chronologically_invalid_view(self) -> None:
        validator = Draft202012Validator(
            json.loads((_SCHEMA_DIR / _RENDERED_VIEW_FILE).read_text()),
            format_checker=FormatChecker(),
        )
        data = _valid_view_data()
        # rendered_at earlier than source_created_at, but both are well-formed.
        data["rendered_at"] = "2020-01-01T00:00:00Z"
        assert list(validator.iter_errors(data)) == []

    def test_runtime_rejects_chronologically_invalid_view(self) -> None:
        sealed = seal_artifact(build_packet())
        with pytest.raises(Exception, match="rendered_at"):
            render_artifact(
                sealed,
                rendered_at=datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC),
                consumer="ci",
            )


class TestRenderedViewSchemaSha256:
    def test_schema_sha256_recorded(self) -> None:
        content = (_SCHEMA_DIR / _RENDERED_VIEW_FILE).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        assert len(digest) == 64
        print(f"rendered-view.schema.json SHA-256: {digest}")
