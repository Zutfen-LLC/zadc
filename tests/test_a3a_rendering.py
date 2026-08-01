"""A3A: rendering foundation — non-authoritative projected views.

Covers the rendered-view contract, the verified-source requirement, the
immutable renderer registry, the public render_artifact entrypoint,
determinism and semantic preservation, adversarial-prose safety, golden
output for all 16 renderer/variant combinations, and the A3A public API
surface.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from pydantic import ValidationError

import zadc
from tests.a2a_factories import (
    build_certification_manifest,
    build_completion_report,
    build_evidence_artifact,
    build_observation,
    build_packet,
)
from tests.a2b1_factories import build_decision_record, build_review_report
from tests.a2b2_factories import build_workflow_bundle
from zadc import (
    DigestMismatchError,
    DigestMissingError,
    Provenance,
    seal_artifact,
    validate_artifact,
    validate_artifact_json,
)
from zadc.canonical import canonical_json_text
from zadc.models.packet import Packet
from zadc.rendering.ci import CI_SOURCE_ARTIFACT_KEY, CiJsonRenderer, _CiPayload
from zadc.rendering.human import (
    HumanMarkdownRenderer,
    _code_fence_for,
    _inline_code,
    _max_backtick_run,
)
from zadc.rendering.models import (
    RENDERED_VIEW_SCHEMA_ID,
    RENDERED_VIEW_VERSION,
    RenderConsumer,
    RenderedView,
    RendererReference,
)
from zadc.rendering.registry import (
    DEFAULT_RENDERER_REGISTRY,
    RendererNotFoundError,
    RendererProtocol,
    RendererRegistry,
    render_artifact,
)

RENDER_AT = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

_VARIANT_BUILDERS = [
    build_packet,
    build_completion_report,
    build_certification_manifest,
    build_evidence_artifact,
    build_observation,
    build_review_report,
    build_decision_record,
    build_workflow_bundle,
]

_VARIANT_TYPES = [
    "packet",
    "completion_report",
    "certification_manifest",
    "evidence_artifact",
    "observation",
    "review_report",
    "decision_record",
    "workflow_bundle",
]


def _sealed(builder: Any) -> Any:
    return seal_artifact(builder())


def _tampered_packet() -> Packet:
    """Return a sealed Packet whose body was mutated after sealing.

    The stored content_digest no longer matches the recomputed digest, so
    verify_content_digest raises DigestMismatchError.
    """
    sealed = seal_artifact(build_packet())
    data = sealed.model_dump(mode="python", by_alias=True)
    data["intent"]["problem_statement"] = "TAMPERED AFTER SEALING"
    return Packet.model_validate(data)


class _ExplodingRenderer:
    """A renderer that raises if render_content is ever called."""

    consumer: RenderConsumer = "human"
    media_type: str = "text/markdown"
    renderer: RendererReference = RendererReference(
        renderer_id="exploding", renderer_version="0.0.1"
    )

    def render_content(self, artifact: Any) -> str:
        raise AssertionError("renderer must not run before source verification")


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------


class TestPublicApi:
    def test_top_level_exports_present(self) -> None:
        for name in [
            "RenderConsumer",
            "RendererReference",
            "RenderedView",
            "RendererProtocol",
            "RendererRegistry",
            "HumanMarkdownRenderer",
            "CiJsonRenderer",
            "DEFAULT_RENDERER_REGISTRY",
            "render_artifact",
            "RendererNotFoundError",
        ]:
            assert name in zadc.__all__, f"{name} missing from zadc.__all__"
            assert hasattr(zadc, name)

    def test_agent_specific_renderers_absent(self) -> None:
        for name in ["HermesRenderer", "CodexRenderer", "ClaudeRenderer"]:
            assert not hasattr(zadc, name)

    def test_render_consumer_vocabulary(self) -> None:
        # mypy cannot introspect a Literal alias at runtime; check the raw args.
        import typing

        args = set(typing.get_args(RenderConsumer))
        assert args == {"human", "ci", "hermes", "codex", "claude"}


# ---------------------------------------------------------------------------
# Verified-source requirement
# ---------------------------------------------------------------------------


class TestVerifiedSourceRequirement:
    def test_unsealed_rejected_with_digest_missing(self) -> None:
        unsealed = build_packet()  # never sealed
        with pytest.raises(DigestMissingError):
            render_artifact(unsealed, rendered_at=RENDER_AT, consumer="human")

    def test_tampered_rejected_with_digest_mismatch(self) -> None:
        tampered = _tampered_packet()
        with pytest.raises(DigestMismatchError):
            render_artifact(tampered, rendered_at=RENDER_AT, consumer="ci")

    def test_verification_runs_before_renderer(self) -> None:
        registry = RendererRegistry((_ExplodingRenderer(),))
        unsealed = build_packet()
        with pytest.raises(DigestMissingError):
            render_artifact(unsealed, rendered_at=RENDER_AT, consumer="human", registry=registry)

    def test_tampered_verification_runs_before_renderer(self) -> None:
        registry = RendererRegistry((_ExplodingRenderer(),))
        with pytest.raises(DigestMismatchError):
            render_artifact(
                _tampered_packet(), rendered_at=RENDER_AT, consumer="human", registry=registry
            )


# ---------------------------------------------------------------------------
# RenderedView contract
# ---------------------------------------------------------------------------


class TestRenderedViewContract:
    def test_source_ref_uses_verified_artifact_id_and_digest(self) -> None:
        sealed = _sealed(build_packet)
        view = render_artifact(sealed, rendered_at=RENDER_AT, consumer="human")
        assert view.source_ref.artifact_id == sealed.artifact_id
        assert view.source_ref.content_digest == sealed.provenance.content_digest

    def test_source_fields_copied_from_source(self) -> None:
        sealed = _sealed(build_workflow_bundle)
        view = render_artifact(sealed, rendered_at=RENDER_AT, consumer="ci")
        assert view.source_artifact_type == sealed.artifact_type
        assert view.source_contract_version == sealed.contract_version
        assert view.source_project_id == sealed.project_id
        assert view.source_slice_id == sealed.slice_id
        assert view.source_slice_instance_id == sealed.slice_instance_id
        assert view.source_policy == sealed.policy

    def test_view_consts(self) -> None:
        view = render_artifact(_sealed(build_packet), rendered_at=RENDER_AT, consumer="human")
        assert view.schema_uri == RENDERED_VIEW_SCHEMA_ID
        assert view.view_version == RENDERED_VIEW_VERSION
        assert view.non_authoritative is True

    def test_renderer_metadata_recorded(self) -> None:
        view = render_artifact(_sealed(build_packet), rendered_at=RENDER_AT, consumer="human")
        assert view.consumer == "human"
        assert view.media_type == "text/markdown"
        assert view.renderer.renderer_id == "zadc-human-markdown"
        assert view.renderer.renderer_version == "0.1.0"
        ci = render_artifact(_sealed(build_packet), rendered_at=RENDER_AT, consumer="ci")
        assert ci.media_type == "application/json"
        assert ci.renderer.renderer_id == "zadc-ci-json"

    def test_view_is_strict_frozen_extra_forbid(self) -> None:
        view = render_artifact(_sealed(build_packet), rendered_at=RENDER_AT, consumer="human")
        with pytest.raises((ValidationError, TypeError, ValueError)):
            view.consumer = "ci"
        with pytest.raises(ValidationError):
            RenderedView.model_validate(
                json.loads(canonical_json_text(view)) | {"unexpected": True}
            )

    def test_view_rejected_by_canonical_adapter(self) -> None:
        view = render_artifact(_sealed(build_packet), rendered_at=RENDER_AT, consumer="ci")
        data = json.loads(canonical_json_text(view))
        with pytest.raises(ValidationError):
            validate_artifact(data)
        with pytest.raises(ValidationError):
            validate_artifact_json(canonical_json_text(view))

    def test_view_has_no_canonical_identity_fields(self) -> None:
        view = render_artifact(_sealed(build_packet), rendered_at=RENDER_AT, consumer="human")
        data = json.loads(canonical_json_text(view))
        # A RenderedView must not carry its own canonical artifact identity.
        assert "artifact_type" not in data
        assert "artifact_id" not in data
        assert "producer" not in data
        assert "provenance" not in data


# ---------------------------------------------------------------------------
# Chronology (runtime-only)
# ---------------------------------------------------------------------------


class TestChronology:
    def test_rendered_at_earlier_than_created_rejected(self) -> None:
        sealed = _sealed(build_packet)  # created_at = 2026-07-31T12:00:00Z
        earlier = datetime(2026, 7, 30, 0, 0, 0, tzinfo=UTC)
        with pytest.raises(ValidationError, match="rendered_at"):
            render_artifact(sealed, rendered_at=earlier, consumer="human")

    def test_rendered_at_equal_created_accepted(self) -> None:
        sealed = _sealed(build_packet)
        equal = sealed.created_at
        view = render_artifact(sealed, rendered_at=equal, consumer="human")
        assert view.rendered_at == sealed.created_at

    def test_rendered_at_later_than_created_accepted(self) -> None:
        sealed = _sealed(build_packet)
        later = datetime(2026, 8, 2, 0, 0, 0, tzinfo=UTC)
        view = render_artifact(sealed, rendered_at=later, consumer="ci")
        assert view.rendered_at == later


# ---------------------------------------------------------------------------
# Renderer registry
# ---------------------------------------------------------------------------


class TestRendererRegistry:
    def test_default_registry_contains_exactly_two_renderers(self) -> None:
        assert set(DEFAULT_RENDERER_REGISTRY.consumers) == {"human", "ci"}
        assert len(DEFAULT_RENDERER_REGISTRY) == 2
        assert "human" in DEFAULT_RENDERER_REGISTRY
        assert "ci" in DEFAULT_RENDERER_REGISTRY
        assert "hermes" not in DEFAULT_RENDERER_REGISTRY

    def test_get_returns_correct_renderer(self) -> None:
        assert isinstance(DEFAULT_RENDERER_REGISTRY.get("human"), HumanMarkdownRenderer)
        assert isinstance(DEFAULT_RENDERER_REGISTRY.get("ci"), CiJsonRenderer)

    def test_get_unregistered_consumer_raises(self) -> None:
        for consumer in ("hermes", "codex", "claude"):
            with pytest.raises(RendererNotFoundError, match=consumer):
                DEFAULT_RENDERER_REGISTRY.get(consumer)

    def test_duplicate_consumer_rejected_at_construction(self) -> None:
        with pytest.raises(ValueError, match="duplicate"):
            RendererRegistry((HumanMarkdownRenderer(), HumanMarkdownRenderer()))

    def test_empty_registry_construction(self) -> None:
        registry = RendererRegistry(())
        assert registry.consumers == ()
        assert len(registry) == 0
        with pytest.raises(RendererNotFoundError):
            registry.get("human")

    def test_registry_is_immutable(self) -> None:
        registry = RendererRegistry((HumanMarkdownRenderer(), CiJsonRenderer()))
        # No public mutation surface exists; attribute writes to __slots__ fail.
        with pytest.raises((AttributeError, TypeError)):
            registry.new_field = True  # type: ignore[attr-defined]

    def test_custom_registry_used_by_render_artifact(self) -> None:
        custom = RendererRegistry((_ExplodingRenderer(),))
        with pytest.raises(AssertionError, match="renderer must not run"):
            render_artifact(
                _sealed(build_packet),
                rendered_at=RENDER_AT,
                consumer="human",
                registry=custom,
            )

    def test_renderers_satisfy_protocol(self) -> None:
        assert isinstance(HumanMarkdownRenderer(), RendererProtocol)
        assert isinstance(CiJsonRenderer(), RendererProtocol)


# ---------------------------------------------------------------------------
# Human Markdown renderer
# ---------------------------------------------------------------------------


class TestHumanMarkdownRenderer:
    def _render(self, builder: Any) -> str:
        return HumanMarkdownRenderer().render_content(_sealed(builder))

    @pytest.mark.parametrize("builder", _VARIANT_BUILDERS)
    def test_all_variants_render(self, builder: Any) -> None:
        content = self._render(builder)
        assert content
        assert content.startswith("# NON-AUTHORITATIVE RENDERED VIEW")

    @pytest.mark.parametrize("builder", _VARIANT_BUILDERS)
    def test_notice_present(self, builder: Any) -> None:
        assert "NON-AUTHORITATIVE" in self._render(builder)

    @pytest.mark.parametrize("builder", _VARIANT_BUILDERS)
    def test_required_source_fields_displayed(self, builder: Any) -> None:
        content = self._render(builder)
        sealed = _sealed(builder)
        # Required display fields appear as labels.
        for label in [
            "Artifact ID",
            "Content digest",
            "Artifact type",
            "Contract version",
            "Project ID",
            "Slice ID",
            "Slice instance ID",
            "Actor ID",
            "Policy ID",
        ]:
            assert label in content
        # The exact source artifact_id and its verified digest appear.
        assert sealed.artifact_id in content
        digest = cast("str", sealed.provenance.content_digest)
        assert digest in content

    def test_review_report_caveat_present(self) -> None:
        content = self._render(build_review_report)
        assert "reviewer judgment" in content
        assert "not authorization" in content

    def test_decision_record_caveat_present(self) -> None:
        content = self._render(build_decision_record)
        assert "recorded decision claim" in content

    def test_workflow_bundle_caveat_present(self) -> None:
        content = self._render(build_workflow_bundle)
        assert "recorded snapshot" in content
        assert "not recomputed" in content

    def test_no_caveat_for_other_variants(self) -> None:
        content = self._render(build_packet)
        assert "reviewer judgment" not in content
        assert "recorded decision claim" not in content

    def test_parent_ids_rendered_when_present(self) -> None:
        parent = "urn:uuid:00000000-0000-0000-0000-000000000099"
        sealed = seal_artifact(build_packet(provenance=Provenance(parent_artifact_ids=(parent,))))
        content = HumanMarkdownRenderer().render_content(sealed)
        assert parent in content
        assert "Parent artifact IDs:" in content

    def test_full_producer_optional_fields_displayed(self) -> None:
        from zadc import ProducerIdentity

        sealed = seal_artifact(
            build_packet(
                producer=ProducerIdentity(
                    actor_type="agent",
                    actor_id="zutfen:agent:hermes",
                    run_id="urn:uuid:00000000-0000-0000-0000-000000000010",
                    model="glm-5.2",
                    provider="zai",
                )
            )
        )
        content = HumanMarkdownRenderer().render_content(sealed)
        assert "urn:uuid:00000000-0000-0000-0000-000000000010" in content
        assert "glm-5.2" in content
        assert "zai" in content

    def test_none_producer_optional_fields_shown_as_none(self) -> None:
        content = self._render(build_packet)
        assert "(none)" in content

    def test_dynamic_fence_handles_backticks(self) -> None:
        # Source-controlled prose with up to five backticks must be fenced safely.
        adversarial = _build_adversarial_packet()
        content = HumanMarkdownRenderer().render_content(adversarial)
        body = _extract_json_block(content)
        # No adversarial structural marker escapes outside the fenced body.
        outside = _strip_code_blocks(content)
        for marker in [
            "# INJECTED HEADING",
            "## INJECTED SUBHEAD",
            "<script>",
            "evil.example.com",
            "broken fence attempt",
        ]:
            assert marker not in outside, f"adversarial marker leaked: {marker!r}"
        # The fence is strictly longer than the longest backtick run in the body.
        assert body.count("`", 0)  # sanity
        fence_len = _fence_length(content)
        assert fence_len > _max_backtick_run(body)

    def test_output_is_deterministic(self) -> None:
        a = self._render(build_packet)
        b = self._render(build_packet)
        assert a == b


# ---------------------------------------------------------------------------
# CI JSON renderer
# ---------------------------------------------------------------------------


class TestCiJsonRenderer:
    def _render(self, builder: Any) -> str:
        return CiJsonRenderer().render_content(_sealed(builder))

    @pytest.mark.parametrize("builder", _VARIANT_BUILDERS)
    def test_all_variants_render_valid_json(self, builder: Any) -> None:
        parsed = json.loads(self._render(builder))
        assert parsed["non_authoritative"] is True
        assert parsed["consumer"] == "ci"
        assert parsed["renderer"]["renderer_id"] == "zadc-ci-json"

    @pytest.mark.parametrize("builder", _VARIANT_BUILDERS)
    def test_payload_carries_required_fields(self, builder: Any) -> None:
        sealed = _sealed(builder)
        parsed = json.loads(self._render(builder))
        assert parsed["schema"] == RENDERED_VIEW_SCHEMA_ID
        assert parsed["contract_version"] == sealed.contract_version
        assert parsed["artifact_type"] == sealed.artifact_type
        assert parsed["project_id"] == sealed.project_id
        assert parsed["slice_id"] == sealed.slice_id
        assert parsed["slice_instance_id"] == sealed.slice_instance_id
        assert parsed["source_ref"]["artifact_id"] == sealed.artifact_id
        assert parsed["source_ref"]["content_digest"] == sealed.provenance.content_digest
        assert parsed["policy"]["policy_id"] == sealed.policy.policy_id
        assert parsed["producer"]["actor_id"] == sealed.producer.actor_id
        assert "content_digest" in parsed["provenance"]
        assert CI_SOURCE_ARTIFACT_KEY in parsed

    @pytest.mark.parametrize("builder", _VARIANT_BUILDERS)
    def test_source_artifact_round_trips(self, builder: Any) -> None:
        sealed = _sealed(builder)
        parsed = json.loads(self._render(builder))
        source = parsed[CI_SOURCE_ARTIFACT_KEY]
        expected = json.loads(canonical_json_text(sealed))
        assert source == expected

    def test_no_markdown_or_ansi_in_output(self) -> None:
        content = self._render(build_packet)
        assert "\x1b[" not in content  # no ANSI escapes
        assert "# " not in content.split("{", 1)[0]

    def test_payload_is_strict(self) -> None:
        # _CiPayload is extra=forbid.
        with pytest.raises(ValidationError):
            _CiPayload.model_validate(
                {"schema": RENDERED_VIEW_SCHEMA_ID}  # incomplete + no extras allowed
            )

    def test_output_is_deterministic(self) -> None:
        a = self._render(build_packet)
        b = self._render(build_packet)
        assert a == b


# ---------------------------------------------------------------------------
# Determinism and semantic preservation
# ---------------------------------------------------------------------------


class TestDeterminismAndSemanticPreservation:
    def test_view_canonical_json_byte_identical_across_runs(self) -> None:
        sealed = _sealed(build_packet)
        a = canonical_json_text(render_artifact(sealed, rendered_at=RENDER_AT, consumer="human"))
        b = canonical_json_text(render_artifact(sealed, rendered_at=RENDER_AT, consumer="human"))
        assert a == b

    def test_list_vs_tuple_construction_invariant(self) -> None:
        from zadc import ArtifactReference
        from zadc.models.completion_report import Changes

        sealed_tuple = seal_artifact(
            build_completion_report(
                changes=Changes(
                    commits=("a" * 40,), files_changed=("x",), dependency_pins_resolved=()
                )
            )
        )
        sealed_list = seal_artifact(
            build_completion_report(
                changes=Changes(
                    commits=["a" * 40],  # type: ignore[arg-type]
                    files_changed=["x"],  # type: ignore[arg-type]
                    dependency_pins_resolved=[],  # type: ignore[arg-type]
                )
            )
        )
        assert sealed_tuple.provenance.content_digest == sealed_list.provenance.content_digest
        assert HumanMarkdownRenderer().render_content(
            sealed_tuple
        ) == HumanMarkdownRenderer().render_content(sealed_list)
        assert CiJsonRenderer().render_content(sealed_tuple) == CiJsonRenderer().render_content(
            sealed_list
        )
        # ArtifactReference import is used to avoid an unused-import lint elsewhere.
        assert ArtifactReference is not None

    def test_field_construction_order_invariant(self) -> None:
        # Build a RendererReference with reversed kwargs order; output is stable.
        r1 = RendererReference(renderer_id="zadc-human-markdown", renderer_version="0.1.0")
        r2 = RendererReference(renderer_version="0.1.0", renderer_id="zadc-human-markdown")
        assert canonical_json_text(r1) == canonical_json_text(r2)

    def test_rendering_does_not_change_source_digest(self) -> None:
        sealed = _sealed(build_workflow_bundle)
        before = canonical_json_text(sealed)
        render_artifact(sealed, rendered_at=RENDER_AT, consumer="human")
        render_artifact(sealed, rendered_at=RENDER_AT, consumer="ci")
        after = canonical_json_text(sealed)
        assert before == after
        assert seal_artifact(sealed).provenance.content_digest == sealed.provenance.content_digest

    def test_same_source_ref_across_renderers(self) -> None:
        sealed = _sealed(build_packet)
        human = render_artifact(sealed, rendered_at=RENDER_AT, consumer="human")
        ci = render_artifact(sealed, rendered_at=RENDER_AT, consumer="ci")
        assert human.source_ref == ci.source_ref


# ---------------------------------------------------------------------------
# Adversarial prose
# ---------------------------------------------------------------------------


# Adversarial prose that passes ConstrainedText validation: no leading/trailing
# whitespace, internal newlines/tabs allowed, no other control chars.
ADV_TEXT = (
    "start # INJECTED HEADING\n"
    "## INJECTED SUBHEAD\n"
    "| col | col |\n"
    "|-----|-----|\n"
    "| a | b |\n"
    "<script>alert('xss')</script>\n"
    "[evil](http://evil.example.com)\n"
    "`one`\n"
    "``two``\n"
    "```three```\n"
    "````four````\n"
    "`````five`````\n"
    "```code\n"
    "broken fence attempt\n"
    "```\n"
    "Unicode café 日本語 ñ ü\n"
    "tab\tvalue\n"
    "end"
)


def _build_adversarial_packet() -> Packet:
    return seal_artifact(
        build_packet(
            intent=__import__("zadc.models.packet", fromlist=["PacketIntent"]).PacketIntent(
                problem_statement=ADV_TEXT, desired_outcome=ADV_TEXT
            ),
            stop_conditions=(ADV_TEXT,),
            deliverables=(ADV_TEXT,),
        )
    )


def _extract_json_block(markdown: str) -> str:
    """Return the content inside the body canonical-JSON code fence."""
    # Find the fence line (longest backtick run) that opens the JSON block.
    lines = markdown.split("\n")
    start = None
    fence_token = None
    for i, line in enumerate(lines):
        if (
            line.startswith("`")
            and line.rstrip().endswith("json")
            and set(line[: -len("json")].strip()) == {"`"}
        ):
            start = i
            fence_token = line[: -len("json")].strip()
            break
    assert start is not None, "no JSON code fence found"
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].strip() == fence_token:
            end = j
            break
    assert end is not None, "JSON code fence not closed"
    return "\n".join(lines[start + 1 : end])


def _strip_code_blocks(markdown: str) -> str:
    """Return markdown with all fenced code blocks removed."""
    lines = markdown.split("\n")
    out: list[str] = []
    in_fence = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```") or (
            stripped.startswith("`") and len(set(stripped)) == 1 and stripped
        ):
            # Toggle on any all-backtick line of length >= 3, or a ```lang line.
            if set(stripped.replace("`", "")) == set() and len(stripped) >= 3:
                in_fence = not in_fence
                continue
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


def _fence_length(markdown: str) -> int:
    """Return the backtick length of the body JSON fence."""
    lines = markdown.split("\n")
    for line in lines:
        if line.startswith("`") and line.rstrip().endswith("json"):
            token = line[: -len("json")].strip()
            if set(token) == {"`"}:
                return len(token)
    return 0


class TestAdversarialProse:
    def test_human_adversarial_remains_data(self) -> None:
        content = HumanMarkdownRenderer().render_content(_build_adversarial_packet())
        # The adversarial heading text appears only inside the fenced JSON body.
        outside = _strip_code_blocks(content)
        assert "# INJECTED HEADING" not in outside
        assert "<script>" not in outside
        assert "evil.example.com" not in outside
        # And it does appear inside the body (as JSON-escaped data).
        body = _extract_json_block(content)
        assert "INJECTED HEADING" in body
        assert "<script>" in body

    def test_ci_adversarial_remains_data(self) -> None:
        artifact = _build_adversarial_packet()
        content = CiJsonRenderer().render_content(artifact)
        parsed = json.loads(content)
        # The adversarial prose round-trips under the source_artifact key.
        source = parsed[CI_SOURCE_ARTIFACT_KEY]
        assert "INJECTED HEADING" in source["intent"]["problem_statement"]
        assert "<script>" in source["intent"]["problem_statement"]

    def test_inline_code_neutralizes_metacharacters(self) -> None:
        wrapped = _inline_code("a`b|c#d<e>[f](g)")
        assert wrapped.startswith("`")
        # The pipe, heading hash, html, and link are inside inline code.
        assert "a`b|c#d<e>[f](g)" in wrapped

    def test_inline_code_padding_for_edge_backticks(self) -> None:
        assert _inline_code("`edge`").startswith("``")
        # Leading/trailing backtick values get space padding inside the span.
        wrapped = _inline_code("`x`")
        assert " " in wrapped

    def test_max_backtick_run(self) -> None:
        assert _max_backtick_run("") == 0
        assert _max_backtick_run("no ticks") == 0
        assert _max_backtick_run("a`b") == 1
        assert _max_backtick_run("``a``") == 2
        assert _max_backtick_run("``a``b```") == 3
        assert _max_backtick_run("``````") == 6

    def test_code_fence_for(self) -> None:
        assert _code_fence_for("plain") == "```"
        assert _code_fence_for("a`b") == "```"
        assert _code_fence_for("```") == "````"
        assert _code_fence_for("````") == "`````"


# ---------------------------------------------------------------------------
# Golden output inventory (16 renderer/variant combinations)
# ---------------------------------------------------------------------------


def _content_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Golden SHA-256 digests of rendered *content* for each (variant, renderer).
# Content excludes rendered_at, so these are stable across runs. Updating them
# is a deliberate, review-visible action.
GOLDEN_CONTENT_DIGESTS: dict[tuple[str, str], str] = {
    ("packet", "human"): "686ed2ba9cfbd5ed51df5833d2893cb93bf218fc2132c1e5e66de60443a20e9c",
    ("packet", "ci"): "8796be0e7df7c7f6609b782d345474f52d103e79d627a329795295b77c99e972",
    (
        "completion_report",
        "human",
    ): "9b0488b1a4a7eb20981cf84866d1a077e9a9e675a4fa4973b00f356fc6664126",
    ("completion_report", "ci"): "f698ca31d78e99b79d8af68d5cf8d9871cf8942f292d7756b3ef171064a14e01",
    (
        "certification_manifest",
        "human",
    ): "efd8571bdbc18081a5763842a2a7b20c85c5b478cb0f123f06632870d9bc47ac",
    (
        "certification_manifest",
        "ci",
    ): "e7795f932db16527ee4a01107a64389e10975a3cf9a805e1a448280c525a22bd",
    (
        "evidence_artifact",
        "human",
    ): "d9717fa9f10d4be8afce0eeb1bd55e387dda30628c6a48b521af12abaed6b2e8",
    ("evidence_artifact", "ci"): "99e2018eea96d4987ab327935c6369b5d33564c7bcdcf13e90728934a3d693c9",
    ("observation", "human"): "3d3be5c161f1b06af9f14b907e2bfac322bce09da3f6baebd4baa6fd71f9b9bd",
    ("observation", "ci"): "2f5b7edbdd655c9e336633fb07b365ee1152139b90618dd17cd129f0c63883d8",
    ("review_report", "human"): "4badce26430c4f0d0ff0fdde9e1bdee05720b4221bb3ae2b066a28388bff97dd",
    ("review_report", "ci"): "7ace119f1ffa0af3698c5e83b10bf740e59060790bd29a09e495944f0471057c",
    (
        "decision_record",
        "human",
    ): "176218edefd738030ec3c96e6f88f60e4b97f86f26614002825911448e9a09b1",
    ("decision_record", "ci"): "137a514bded7021ab06afa440d0dafbc5788294bd5b282d40eb8a8d39eabb3db",
    (
        "workflow_bundle",
        "human",
    ): "4e0ada3cd09031af82989680fde5aa18ce26e8df82c9dab66ad48701eb886549",
    ("workflow_bundle", "ci"): "0d254e8781e9457140e7d022487a1e04b130fe16df146607982b4f9236b97cc6",
}


_VARIANT_PAIRS: list[tuple[str, Any]] = list(zip(_VARIANT_TYPES, _VARIANT_BUILDERS, strict=True))


@pytest.mark.parametrize("variant,builder", _VARIANT_PAIRS)
class TestGoldenOutput:
    def test_human_golden(self, variant: str, builder: Any) -> None:
        content = HumanMarkdownRenderer().render_content(_sealed(builder))
        digest = _content_digest(content)
        assert digest == GOLDEN_CONTENT_DIGESTS[(variant, "human")], (
            f"human {variant} golden digest changed: {digest}"
        )

    def test_ci_golden(self, variant: str, builder: Any) -> None:
        content = CiJsonRenderer().render_content(_sealed(builder))
        digest = _content_digest(content)
        assert digest == GOLDEN_CONTENT_DIGESTS[(variant, "ci")], (
            f"ci {variant} golden digest changed: {digest}"
        )
