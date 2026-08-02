"""Renderer protocol, immutable registry, and the public render entrypoint (A3A).

Defines:

- :class:`RendererProtocol` — a runtime-checkable, narrowly typed protocol
  every renderer implementation satisfies. Renderers return content only; the
  shared :func:`render_artifact` wrapper performs source verification and
  constructs the :class:`~zadc.rendering.models.RenderedView`.
- :class:`RendererNotFoundError` — the public error raised when no renderer is
  registered for a requested consumer.
- :class:`RendererRegistry` — an immutable registry built from an explicit,
  finite renderer sequence. Duplicate consumer registrations are rejected at
  construction; there is no mutable registration surface afterward. Lookup
  failure raises :class:`RendererNotFoundError`.
- :data:`DEFAULT_RENDERER_REGISTRY` — the registry containing exactly
  :class:`~zadc.rendering.human.HumanMarkdownRenderer`,
  :class:`~zadc.rendering.ci.CiJsonRenderer`, and
  :class:`~zadc.rendering.hermes.HermesRenderer`.
- :func:`render_artifact` — the public entrypoint that verifies the source
  content digest, selects a renderer by consumer, renders content, and
  constructs a bound :class:`~zadc.rendering.models.RenderedView`.

No entry-point discovery, dynamic imports, plugins, filesystem scanning, or
network loading is performed. ``codex`` and ``claude`` are part of the
:data:`~zadc.rendering.models.RenderConsumer` vocabulary but have no
registered renderer in A3B1; requests for them fail explicitly.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Optional, Protocol, runtime_checkable

from zadc.digests import verify_content_digest
from zadc.models.artifact_union import ZadcArtifact
from zadc.models.shared import ArtifactReference
from zadc.rendering.ci import CiJsonRenderer
from zadc.rendering.hermes import HermesRenderer
from zadc.rendering.human import HumanMarkdownRenderer
from zadc.rendering.models import (
    RENDERED_VIEW_SCHEMA_ID,
    RENDERED_VIEW_VERSION,
    RenderConsumer,
    RenderedView,
    RendererReference,
)
from zadc.types import MediaType


@runtime_checkable
class RendererProtocol(Protocol):
    """The narrow interface every renderer implementation satisfies.

    Implementations expose their fixed consumer, media type, and stable
    renderer identity, plus a single :meth:`render_content` method that
    returns content only. Renderers receive no mutable global context and
    must produce deterministic output for a given verified artifact and
    renderer version.
    """

    @property
    def consumer(self) -> RenderConsumer:
        """Return the consumer for this renderer."""
        ...

    @property
    def media_type(self) -> MediaType:
        """Return the output media type for this renderer."""
        ...

    @property
    def renderer(self) -> RendererReference:
        """Return the stable renderer identity."""
        ...

    def render_content(self, artifact: ZadcArtifact) -> str:
        """Return the rendered content for a verified ``artifact``."""
        ...


class RendererNotFoundError(Exception):
    """Raised when no renderer is registered for a requested consumer.

    Carries only the requested consumer name — never an artifact payload.
    """

    def __init__(self, consumer: str) -> None:
        self.consumer = consumer
        super().__init__(f"no renderer registered for consumer {consumer!r}")


@dataclass(frozen=True, slots=True)
class _RendererRegistration:
    """An immutable snapshot of one renderer registration."""

    consumer: RenderConsumer
    media_type: MediaType
    renderer: RendererReference
    _render_content: Callable[[ZadcArtifact], str] = field(repr=False, compare=False)

    def render_content(self, artifact: ZadcArtifact) -> str:
        """Render content with the callable captured during registration."""
        return self._render_content(artifact)


class RendererRegistry:
    """An immutable registry mapping consumers to registration snapshots.

    Constructed from an explicit, finite renderer sequence. Duplicate consumer
    registrations are rejected at construction. Each registration snapshots
    its consumer, media type, renderer identity, and render callable. Later
    changes to an input renderer's metadata cannot change the registry. After
    construction, the registry exposes no mutation surface. Lookup for an
    unregistered consumer raises :class:`RendererNotFoundError`.
    """

    __slots__ = ("_renderers",)

    def __init__(self, renderers: Sequence[RendererProtocol]) -> None:
        mapping: dict[RenderConsumer, _RendererRegistration] = {}
        for renderer in renderers:
            consumer = renderer.consumer
            if consumer in mapping:
                raise ValueError(
                    f"duplicate renderer for consumer {consumer!r}: "
                    f"{mapping[consumer].renderer.renderer_id!r} and "
                    f"{renderer.renderer.renderer_id!r}"
                )
            renderer_reference = RendererReference(
                renderer_id=renderer.renderer.renderer_id,
                renderer_version=renderer.renderer.renderer_version,
            )
            mapping[consumer] = _RendererRegistration(
                consumer=consumer,
                media_type=renderer.media_type,
                renderer=renderer_reference,
                _render_content=renderer.render_content,
            )
        self._renderers: MappingProxyType[RenderConsumer, _RendererRegistration] = MappingProxyType(
            mapping
        )

    def get(self, consumer: RenderConsumer) -> RendererProtocol:
        """Return the renderer registered for ``consumer``.

        Raises:
            RendererNotFoundError: If no renderer is registered for the
                requested consumer (including the reserved-but-unimplemented
                ``codex`` and ``claude`` consumers).
        """
        if consumer in self._renderers:
            return self._renderers[consumer]
        raise RendererNotFoundError(consumer)

    @property
    def consumers(self) -> tuple[RenderConsumer, ...]:
        """The consumers with a registered renderer, in registration order."""
        return tuple(self._renderers)

    def __len__(self) -> int:
        return len(self._renderers)

    def __contains__(self, consumer: object) -> bool:
        return consumer in self._renderers


#: The default registry for A3B1: exactly the human Markdown, CI JSON, and
#: Hermes Markdown renderers, in deterministic registration order. ``codex``
#: and ``claude`` are deliberately absent until A3B2/A3B3.
DEFAULT_RENDERER_REGISTRY: RendererRegistry = RendererRegistry(
    (HumanMarkdownRenderer(), CiJsonRenderer(), HermesRenderer())
)


def render_artifact(
    artifact: ZadcArtifact,
    *,
    rendered_at: datetime,
    consumer: RenderConsumer,
    registry: Optional[RendererRegistry] = None,
) -> RenderedView:
    """Render a verified canonical artifact into a non-authoritative view.

    Verifies the source content digest *before* selecting or running any
    renderer, so unsealed sources raise
    :class:`~zadc.errors.DigestMissingError` and tampered sources raise
    :class:`~zadc.errors.DigestMismatchError` before a renderer ever runs.
    The renderer is then selected from ``registry`` (defaulting to
    :data:`DEFAULT_RENDERER_REGISTRY`) by ``consumer``; an unregistered
    consumer raises :class:`RendererNotFoundError`.

    Every ``source_*`` field of the returned view is copied directly from the
    verified source artifact. ``source_ref`` uses the source ``artifact_id``
    and the verified ``provenance.content_digest``. The source artifact and
    its canonical serialization are left byte-identical.

    Args:
        artifact: A concrete ZADC artifact (one of the eight variants).
        rendered_at: Explicit render timestamp; MUST NOT precede the source
            artifact's ``created_at``.
        consumer: The render consumer to select a renderer for.
        registry: Optional registry override. Defaults to
            :data:`DEFAULT_RENDERER_REGISTRY`.

    Returns:
        A bound, non-authoritative :class:`RenderedView`.

    Raises:
        DigestMissingError: If the source has not been sealed.
        DigestMismatchError: If the source was modified after sealing.
        RendererNotFoundError: If ``consumer`` has no registered renderer.
        ValueError: If ``rendered_at`` precedes ``source_created_at``.
    """
    verified_digest = verify_content_digest(artifact)

    active_registry = registry if registry is not None else DEFAULT_RENDERER_REGISTRY
    renderer = active_registry.get(consumer)

    content = renderer.render_content(artifact)

    return RenderedView(
        schema=RENDERED_VIEW_SCHEMA_ID,
        view_version=RENDERED_VIEW_VERSION,
        non_authoritative=True,
        consumer=consumer,
        media_type=renderer.media_type,
        renderer=renderer.renderer,
        rendered_at=rendered_at,
        source_ref=ArtifactReference(
            artifact_id=artifact.artifact_id,
            content_digest=verified_digest,
        ),
        source_artifact_type=artifact.artifact_type,
        source_contract_version=artifact.contract_version,
        source_created_at=artifact.created_at,
        source_project_id=artifact.project_id,
        source_slice_id=artifact.slice_id,
        source_slice_instance_id=artifact.slice_instance_id,
        source_policy=artifact.policy,
        content=content,
    )


__all__ = [
    "DEFAULT_RENDERER_REGISTRY",
    "RendererNotFoundError",
    "RendererProtocol",
    "RendererRegistry",
    "render_artifact",
]
