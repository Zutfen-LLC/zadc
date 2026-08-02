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
from zadc.rendering.hermes import HermesRenderer
from zadc.rendering.human import (
    HumanMarkdownRenderer,
    _code_fence_for,
    _escape_summary_value,
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


class _MutableRenderer:
    """A mutable renderer used to test registry metadata snapshots."""

    def __init__(self) -> None:
        self.consumer: RenderConsumer = "human"
        self.media_type = "text/markdown"
        self.renderer = RendererReference(renderer_id="mutable-renderer", renderer_version="0.0.1")

    def render_content(self, artifact: Any) -> str:
        return f"custom:{artifact.artifact_id}"


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
            "HermesRenderer",
            "DEFAULT_RENDERER_REGISTRY",
            "render_artifact",
            "RendererNotFoundError",
        ]:
            assert name in zadc.__all__, f"{name} missing from zadc.__all__"
            assert hasattr(zadc, name)

    def test_agent_specific_renderers_absent(self) -> None:
        for name in ["CodexRenderer", "ClaudeRenderer"]:
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
        assert set(DEFAULT_RENDERER_REGISTRY.consumers) == {"human", "ci", "hermes"}
        assert len(DEFAULT_RENDERER_REGISTRY) == 3
        assert "human" in DEFAULT_RENDERER_REGISTRY
        assert "ci" in DEFAULT_RENDERER_REGISTRY
        assert "hermes" in DEFAULT_RENDERER_REGISTRY
        assert "codex" not in DEFAULT_RENDERER_REGISTRY

    def test_get_returns_correct_renderer(self) -> None:
        human = DEFAULT_RENDERER_REGISTRY.get("human")
        ci = DEFAULT_RENDERER_REGISTRY.get("ci")
        assert isinstance(human, RendererProtocol)
        assert human.consumer == "human"
        assert human.media_type == "text/markdown"
        assert human.renderer == RendererReference(
            renderer_id="zadc-human-markdown", renderer_version="0.1.0"
        )
        assert isinstance(ci, RendererProtocol)
        assert ci.consumer == "ci"
        assert ci.media_type == "application/json"
        assert ci.renderer == RendererReference(
            renderer_id="zadc-ci-json", renderer_version="0.1.0"
        )

    def test_get_unregistered_consumer_raises(self) -> None:
        for consumer in ("codex", "claude"):
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

    @pytest.mark.parametrize("consumer", ["human", "ci", "hermes"])
    @pytest.mark.parametrize("attribute", ["consumer", "media_type", "renderer"])
    def test_default_registration_metadata_is_immutable(
        self, consumer: RenderConsumer, attribute: str
    ) -> None:
        registered = DEFAULT_RENDERER_REGISTRY.get(consumer)
        before = registered.render_content(_sealed(build_packet))
        with pytest.raises((AttributeError, TypeError)):
            setattr(registered, attribute, "replacement")
        assert registered.render_content(_sealed(build_packet)) == before

    @pytest.mark.parametrize(
        "renderer", [HumanMarkdownRenderer(), CiJsonRenderer(), HermesRenderer()]
    )
    @pytest.mark.parametrize("attribute", ["consumer", "media_type", "renderer"])
    def test_builtin_renderer_metadata_is_immutable(
        self, renderer: RendererProtocol, attribute: str
    ) -> None:
        with pytest.raises((AttributeError, TypeError)):
            setattr(renderer, attribute, "replacement")

    def test_custom_registration_is_immutable_and_snapshots_metadata(self) -> None:
        supplied = _MutableRenderer()
        registry = RendererRegistry((supplied,))
        registered = registry.get("human")

        for attribute in ("consumer", "media_type", "renderer"):
            with pytest.raises((AttributeError, TypeError)):
                setattr(registered, attribute, "replacement")

        supplied.consumer = "ci"
        supplied.media_type = "application/json"
        supplied.renderer = RendererReference(
            renderer_id="changed-renderer", renderer_version="9.9.9"
        )

        assert registry.consumers == ("human",)
        assert registered.consumer == "human"
        assert registered.media_type == "text/markdown"
        assert registered.renderer == RendererReference(
            renderer_id="mutable-renderer", renderer_version="0.0.1"
        )

        view = render_artifact(
            _sealed(build_packet),
            rendered_at=RENDER_AT,
            consumer="human",
            registry=registry,
        )
        assert view.consumer == registered.consumer
        assert view.media_type == registered.media_type
        assert view.renderer == registered.renderer

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
        assert isinstance(HermesRenderer(), RendererProtocol)


# ---------------------------------------------------------------------------
# Fixed built-in renderer identities
# ---------------------------------------------------------------------------


_REPLACEMENT_RENDERER = RendererReference(renderer_id="impostor", renderer_version="9.9.9")

#: Identity override attempts that must be rejected by every built-in
#: renderer constructor. ``consumer`` swaps the documented consumer, the
#: ``media_type`` value is a real media type, and ``renderer`` is a valid
#: :class:`RendererReference`; all are rejected only because the identity
#: fields are non-configurable (``init=False``).
_IDENTITY_OVERRIDES: list[dict[str, Any]] = [
    {"consumer": "ci"},
    {"media_type": "application/octet-stream"},
    {"renderer": _REPLACEMENT_RENDERER},
    {
        "consumer": "human",
        "media_type": "application/json",
        "renderer": _REPLACEMENT_RENDERER,
    },
]


@pytest.mark.parametrize("renderer_cls", [HumanMarkdownRenderer, CiJsonRenderer, HermesRenderer])
@pytest.mark.parametrize("identity_override", _IDENTITY_OVERRIDES)
def test_builtin_constructors_reject_identity_overrides(
    renderer_cls: type, identity_override: dict[str, Any]
) -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        renderer_cls(**identity_override)


@pytest.mark.parametrize(
    "renderer_cls",
    [HumanMarkdownRenderer, CiJsonRenderer, HermesRenderer],
)
def test_builtin_constructors_accept_no_arguments(renderer_cls: type) -> None:
    # The argument-free constructor is the only construction surface.
    instance = renderer_cls()
    assert isinstance(instance, RendererProtocol)


def test_human_markdown_exposes_documented_identity() -> None:
    renderer = HumanMarkdownRenderer()
    assert renderer.consumer == "human"
    assert renderer.media_type == "text/markdown"
    assert renderer.renderer == RendererReference(
        renderer_id="zadc-human-markdown", renderer_version=RENDERED_VIEW_VERSION
    )


def test_ci_json_exposes_documented_identity() -> None:
    renderer = CiJsonRenderer()
    assert renderer.consumer == "ci"
    assert renderer.media_type == "application/json"
    assert renderer.renderer == RendererReference(
        renderer_id="zadc-ci-json", renderer_version=RENDERED_VIEW_VERSION
    )


@pytest.mark.parametrize("builder", _VARIANT_BUILDERS)
def test_ci_content_identity_equals_enclosing_view_metadata(builder: Any) -> None:
    sealed = _sealed(builder)
    view = render_artifact(sealed, rendered_at=RENDER_AT, consumer="ci")
    parsed = json.loads(view.content)
    # The machine-readable CI payload carries the same consumer and renderer
    # identity recorded by the enclosing RenderedView projection metadata.
    assert parsed["consumer"] == view.consumer
    assert parsed["renderer"]["renderer_id"] == view.renderer.renderer_id
    assert parsed["renderer"]["renderer_version"] == view.renderer.renderer_version


def test_ci_content_identity_equals_view_metadata_for_explicit_registry() -> None:
    # A registry built from a fresh built-in instance must still agree with the
    # content payload, since both are derived from the same fixed identity.
    sealed = _sealed(build_packet)
    registry = RendererRegistry((CiJsonRenderer(),))
    view = render_artifact(sealed, rendered_at=RENDER_AT, consumer="ci", registry=registry)
    parsed = json.loads(view.content)
    assert parsed["consumer"] == view.consumer
    assert parsed["renderer"] == {
        "renderer_id": view.renderer.renderer_id,
        "renderer_version": view.renderer.renderer_version,
    }


def test_default_registry_rendering_is_deterministic() -> None:
    sealed = _sealed(build_packet)
    consumers: tuple[RenderConsumer, ...] = ("human", "ci", "hermes")
    for consumer in consumers:
        first = render_artifact(sealed, rendered_at=RENDER_AT, consumer=consumer).content
        second = render_artifact(sealed, rendered_at=RENDER_AT, consumer=consumer).content
        assert first == second


def test_custom_registry_rendering_is_deterministic() -> None:
    sealed = _sealed(build_packet)
    registry = RendererRegistry((_MutableRenderer(),))
    first = render_artifact(
        sealed, rendered_at=RENDER_AT, consumer="human", registry=registry
    ).content
    second = render_artifact(
        sealed, rendered_at=RENDER_AT, consumer="human", registry=registry
    ).content
    assert first == second
    # The custom renderer's fixed metadata is reflected verbatim in the view.
    view = render_artifact(sealed, rendered_at=RENDER_AT, consumer="human", registry=registry)
    assert view.renderer.renderer_id == "mutable-renderer"


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

    def test_producer_summary_values_are_single_line_and_escaped(self) -> None:
        from zadc import ProducerIdentity

        model = (
            "model-start\n# MODEL HEADING\r> model quote\t| a | b | "
            "<script>model</script> [model](https://evil.example/model) "
            '\\path "quoted" ```model-fence```\u0001'
        )
        provider = (
            "provider-start\n## PROVIDER HEADING\r> provider quote\n"
            "- provider list\t| x | y | "
            "<table><tr><td>provider</td></tr></table> "
            '[provider](https://evil.example/provider) \\provider "provider-quoted" '
            "````provider-fence````\u0002"
        )
        sealed = seal_artifact(
            build_packet(
                producer=ProducerIdentity(
                    actor_type="agent",
                    actor_id="zutfen:agent:hostile",
                    model=model,
                    provider=provider,
                )
            )
        )

        content = HumanMarkdownRenderer().render_content(sealed)
        outside = _strip_code_blocks(content)
        model_line = next(line for line in outside.splitlines() if line.startswith("- **Model:**"))
        provider_line = next(
            line for line in outside.splitlines() if line.startswith("- **Provider:**")
        )

        assert model not in outside
        assert provider not in outside
        assert "\r" not in outside
        for summary_line in (model_line, provider_line):
            assert "\\n" in summary_line
            assert "\\r" in summary_line
            assert "\\t" in summary_line
        assert "\\\\path" in model_line
        assert '\\"quoted\\"' in model_line
        assert "\\u0001" in model_line
        assert "\\\\provider" in provider_line
        assert '\\"provider-quoted\\"' in provider_line
        assert "\\u0002" in provider_line

        for line in outside.splitlines():
            assert not line.startswith(
                ("# MODEL", "## PROVIDER", "> model", "> provider", "- provider")
            )
            assert not line.startswith(("|", "<script>", "<table>", "[model]", "[provider]"))
            assert not line.startswith(("```model", "````provider"))

        source = json.loads(_extract_json_block(content))
        assert source["producer"]["model"] == model
        assert source["producer"]["provider"] == provider

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
        assert "schema" not in parsed
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
        parsed = json.loads(self._render(build_packet))
        with pytest.raises(ValidationError):
            _CiPayload.model_validate(parsed | {"unexpected": True})

    def test_payload_is_frozen(self) -> None:
        payload = _CiPayload.model_validate(json.loads(self._render(build_packet)))
        with pytest.raises((ValidationError, TypeError, ValueError)):
            payload.consumer = "human"  # type: ignore[assignment]

    def test_enclosing_view_keeps_rendered_view_schema(self) -> None:
        view = render_artifact(_sealed(build_packet), rendered_at=RENDER_AT, consumer="ci")
        assert view.schema_uri == RENDERED_VIEW_SCHEMA_ID
        assert "schema" not in json.loads(view.content)

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

    def test_summary_escape_is_reversible_and_single_line(self) -> None:
        value = 'line 1\nline 2\r\ttab \\path "quoted"\u0003'
        escaped = _escape_summary_value(value)
        assert "\n" not in escaped
        assert "\r" not in escaped
        assert json.loads(f'"{escaped}"') == value

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
    ("packet", "ci"): "c76977c76780b905e7bb5fb06fb1bbdf6ba8bde5cc563282c5799e051102d36a",
    (
        "completion_report",
        "human",
    ): "9b0488b1a4a7eb20981cf84866d1a077e9a9e675a4fa4973b00f356fc6664126",
    ("completion_report", "ci"): "bced740eb2177510f9ded7b2f5024c19a42db63b03316eeea1bd228927557c15",
    (
        "certification_manifest",
        "human",
    ): "efd8571bdbc18081a5763842a2a7b20c85c5b478cb0f123f06632870d9bc47ac",
    (
        "certification_manifest",
        "ci",
    ): "a4943b4cc8018d2e0909d4188caeaccd698082c9017ec74ef727f297f6111468",
    (
        "evidence_artifact",
        "human",
    ): "d9717fa9f10d4be8afce0eeb1bd55e387dda30628c6a48b521af12abaed6b2e8",
    ("evidence_artifact", "ci"): "cdce0520f90cd88f52c0324fa5bbc081af183e0d6d55ab22b0cd4cf20175bc7c",
    ("observation", "human"): "3d3be5c161f1b06af9f14b907e2bfac322bce09da3f6baebd4baa6fd71f9b9bd",
    ("observation", "ci"): "c2292349d73ea1262a54c6b1ffe84d17219decbd7cbf31959298b8dd03b86263",
    ("review_report", "human"): "4badce26430c4f0d0ff0fdde9e1bdee05720b4221bb3ae2b066a28388bff97dd",
    ("review_report", "ci"): "3a41084ff6993da9a3e697372f96c2f3a43623729cf55efb735f3d793b41af37",
    (
        "decision_record",
        "human",
    ): "176218edefd738030ec3c96e6f88f60e4b97f86f26614002825911448e9a09b1",
    ("decision_record", "ci"): "31117320609de757b3b307d75d21889e93f41af054770b323331f8cebf136540",
    (
        "workflow_bundle",
        "human",
    ): "4e0ada3cd09031af82989680fde5aa18ce26e8df82c9dab66ad48701eb886549",
    ("workflow_bundle", "ci"): "2ef8f2f629bc7db5842872cf58f13535b63a54b1451f29a42bdfe71ff25e2b03",
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
