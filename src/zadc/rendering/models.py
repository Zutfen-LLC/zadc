"""Non-authoritative rendered-view models for ZADC (A3A).

This module defines the deterministic, non-authoritative projection records
that sit *beside* the canonical artifact substrate, never inside it. A
:class:`RenderedView` is bound to exactly one verified sealed canonical
artifact by exact artifact ID and content digest, but it carries no artifact
identity, content digest, producer, authority, approval, or lifecycle state
of its own.

Contract references:
    - Architecture section 8.16 (Rendered view): a rendered view is not
      authoritative and MUST carry the canonical artifact identifier and
      digest from which it was produced.
    - Architecture section 19.0: every rendering MUST include the canonical
      artifact ID and digest and MUST be reproducibly generated from the same
      source.

Design constraints honored here:
    - :class:`RenderedView` reuses the existing strict, frozen,
      ``extra="forbid"`` model configuration. It is a projection record, not
      a canonical artifact, and is never added to ``ArtifactType`` or
      ``ZadcArtifact``.
    - No field here calls the current clock; ``rendered_at`` is explicit
      caller input supplied through :func:`zadc.rendering.render_artifact`.
    - The ``rendered_at >= source_created_at`` chronology invariant is a
      comparison between two arbitrary timestamp values and has no standard
      JSON Schema vocabulary. It is enforced at runtime only
      (:meth:`RenderedView._check_chronology`) and documented as such.
"""

from typing import Literal

from pydantic import Field, model_validator

from zadc.models.common import PolicyReference, _ZadcModel
from zadc.models.shared import ArtifactReference
from zadc.types import (
    CONTRACT_VERSION,
    ArtifactType,
    GlobalId,
    MediaType,
    SliceId,
    StableId,
    Timestamp,
)

#: The canonical JSON Schema $id for the rendered-view projection record.
RENDERED_VIEW_SCHEMA_ID: str = "https://schemas.zutfen.com/zadc/0.1/rendered-view.schema.json"

#: The rendered-view schema version (parallel to the canonical contract version).
RENDERED_VIEW_VERSION: str = "0.1.0"

#: The complete architecture-level render-consumer vocabulary. A3A supplies
#: default renderers only for ``human`` and ``ci``; ``hermes``, ``codex``, and
#: ``claude`` are reserved for A3B so the public enum does not change when
#: those implementations land. Requests for a consumer with no registered
#: renderer fail explicitly (see
#: :class:`zadc.rendering.registry.RendererNotFoundError`).
RenderConsumer = Literal["human", "ci", "hermes", "codex", "claude"]


class RendererReference(_ZadcModel):
    """Stable, explicit identity for one renderer implementation.

    Used by every :class:`RenderedView` to record which renderer produced its
    content, so a consumer can independently judge whether to trust a given
    projection's presentation. The default renderers use:

    - ``zadc-human-markdown @ 0.1.0``
    - ``zadc-ci-json @ 0.1.0``
    """

    renderer_id: StableId
    renderer_version: StableId


class RenderedView(_ZadcModel):
    """A non-authoritative projection of one verified sealed canonical artifact.

    A ``RenderedView`` is a presentation record: it reproduces selected
    metadata copied directly from its single source artifact plus rendered
    ``content`` produced by a deterministic renderer. It is **not** an
    :class:`~zadc.models.common.ArtifactEnvelope`: it carries no
    ``artifact_type``, ``artifact_id``, ``producer``, ``provenance``,
    authority, approval, lifecycle state, or canonical content digest of its
    own. The only content digest it carries is the *source's*, recorded in
    ``source_ref`` and copied from the source's verified
    ``provenance.content_digest``.

    Rendering does not authenticate identities, reconcile live state, verify
    references, derive lifecycle state, approve merges, or accept risk. Those
    remain canonical-authority concerns governed by later slices.
    """

    schema_uri: Literal[RENDERED_VIEW_SCHEMA_ID] = Field(alias="schema")  # type: ignore[valid-type]
    view_version: Literal[RENDERED_VIEW_VERSION]  # type: ignore[valid-type]
    non_authoritative: Literal[True]
    consumer: RenderConsumer
    media_type: MediaType
    renderer: RendererReference
    rendered_at: Timestamp
    source_ref: ArtifactReference
    source_artifact_type: ArtifactType
    source_contract_version: Literal[CONTRACT_VERSION]  # type: ignore[valid-type]
    source_created_at: Timestamp
    source_project_id: GlobalId
    source_slice_id: SliceId
    source_slice_instance_id: SliceId
    source_policy: PolicyReference
    content: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_chronology(self) -> "RenderedView":
        """Runtime-only: ``rendered_at`` must not precede ``source_created_at``.

        This is a comparison between two arbitrary timestamp values, which has
        no standard JSON Schema vocabulary, so it cannot be expressed in the
        generated schema. It is enforced here at construction time only. An
        equal or later ``rendered_at`` is accepted.
        """
        if self.rendered_at < self.source_created_at:
            raise ValueError("rendered_at must not precede source_created_at")
        return self


__all__ = [
    "RENDERED_VIEW_SCHEMA_ID",
    "RENDERED_VIEW_VERSION",
    "RenderConsumer",
    "RendererReference",
    "RenderedView",
]
