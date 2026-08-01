"""ZADC rendering layer — non-authoritative projected views (A3A).

A deterministic, non-authoritative rendering layer over the eight canonical
ZADC artifacts. Every view remains bound to a verified sealed source artifact
by exact artifact ID and content digest, without altering, interpreting, or
replacing canonical authority semantics.

Public API:
    Types:
        RenderConsumer  — the render-consumer vocabulary (human, ci, hermes,
                          codex, claude).
    Models:
        RendererReference — stable identity for one renderer implementation.
        RenderedView      — a non-authoritative projection record.
    Interfaces:
        RendererProtocol  — the narrow protocol every renderer satisfies.
        RendererRegistry  — an immutable consumer-to-renderer registry.
    Renderers:
        HumanMarkdownRenderer — human-readable Markdown (consumer ``human``).
        CiJsonRenderer        — machine-neutral canonical JSON (consumer ``ci``).
    Constants:
        DEFAULT_RENDERER_REGISTRY — exactly the two default renderers.
        RENDERED_VIEW_SCHEMA_ID   — the rendered-view schema $id.
        RENDERED_VIEW_VERSION     — the rendered-view version.
    Functions:
        render_artifact — verify, select, render, and construct a view.
    Errors:
        RendererNotFoundError — no renderer registered for a consumer.
"""

from zadc.rendering.ci import CI_SOURCE_ARTIFACT_KEY, CiJsonRenderer
from zadc.rendering.human import HumanMarkdownRenderer
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

__all__ = [
    "CI_SOURCE_ARTIFACT_KEY",
    "DEFAULT_RENDERER_REGISTRY",
    "RENDERED_VIEW_SCHEMA_ID",
    "RENDERED_VIEW_VERSION",
    "CiJsonRenderer",
    "HumanMarkdownRenderer",
    "RenderConsumer",
    "RenderedView",
    "RendererNotFoundError",
    "RendererProtocol",
    "RendererReference",
    "RendererRegistry",
    "render_artifact",
]
