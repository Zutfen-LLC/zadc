"""The machine-neutral CI JSON renderer (A3A-08).

Produces deterministic ZADC Canonical JSON for any of the eight canonical
artifacts. The payload is a strict, frozen, ``extra="forbid"`` projection
record that carries the non-authoritative marker, the exact verified
``source_ref``, the copied source identity/producer/provenance/policy
metadata, and the complete canonical source artifact payload under a single
documented key (``source_artifact``).

Parsing the rendered content with ``json.loads`` reproduces the exact source
artifact data under the ``source_artifact`` key. The renderer never calls the
clock, never mutates its source, and never converts recorded derived state or
recommendations into CI success/failure — it only embeds what the source
already recorded.

Like the human renderer, this method is invoked only after
:func:`zadc.rendering.render_artifact` has verified the source content digest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, cast

from zadc.canonical import canonical_json_text
from zadc.models.artifact_union import ZadcArtifact
from zadc.models.common import PolicyReference, ProducerIdentity, Provenance, _ZadcModel
from zadc.models.shared import ArtifactReference
from zadc.rendering.models import (
    RENDERED_VIEW_VERSION,
    RendererReference,
)
from zadc.types import (
    CONTRACT_VERSION,
    ArtifactType,
    GlobalId,
    MediaType,
    SliceId,
)

#: The single documented key under which the complete canonical source
#: artifact payload is embedded in every CI rendering.
CI_SOURCE_ARTIFACT_KEY: str = "source_artifact"

_CI_RENDERER_REFERENCE = RendererReference(
    renderer_id="zadc-ci-json",
    renderer_version=RENDERED_VIEW_VERSION,
)


class _CiPayload(_ZadcModel):
    """Strict internal payload model for the CI rendering.

    Carries the non-authoritative marker, the exact verified ``source_ref``,
    copied source identity/producer/provenance/policy metadata, and the
    complete canonical source artifact payload. ``extra="forbid"`` (inherited)
    prevents arbitrary extension keys.
    """

    non_authoritative: Literal[True]
    consumer: Literal["ci"]
    renderer: RendererReference
    source_ref: ArtifactReference
    artifact_type: ArtifactType
    contract_version: Literal[CONTRACT_VERSION]  # type: ignore[valid-type]
    project_id: GlobalId
    slice_id: SliceId
    slice_instance_id: SliceId
    policy: PolicyReference
    producer: ProducerIdentity
    provenance: Provenance
    source_artifact: ZadcArtifact


@dataclass(frozen=True, slots=True)
class CiJsonRenderer:
    """Deterministic machine-neutral canonical-JSON renderer for all eight artifacts.

    Identity: consumer ``ci``, media type ``application/json``,
    ``zadc-ci-json @ 0.1.0``. Stateless — output depends only on the verified
    source artifact and the renderer version.

    The identity fields (``consumer``, ``media_type``, ``renderer``) are
    :func:`~dataclasses.field` declarations with ``init=False`` and fixed
    defaults. The generated constructor therefore takes no arguments, so the
    documented identity can be neither replaced at construction nor changed
    afterward. The CI content payload is derived from these same fields, so the
    enclosing :class:`~zadc.rendering.models.RenderedView` projection metadata
    and the machine-readable content can never disagree.
    """

    consumer: Literal["ci"] = field(default="ci", init=False)
    media_type: MediaType = field(default="application/json", init=False)
    renderer: RendererReference = field(default=_CI_RENDERER_REFERENCE, init=False)

    def render_content(self, artifact: ZadcArtifact) -> str:
        """Return the deterministic canonical-JSON projection of ``artifact``.

        ``artifact`` MUST already be content-digest verified by
        :func:`zadc.rendering.render_artifact`; this method does not re-verify
        and never mutates its input.
        """
        # render_artifact verifies the artifact before invoking this renderer,
        # so content_digest is guaranteed present and matches the recomputed
        # digest. The cast records that precondition for the type checker.
        verified_digest = cast("str", artifact.provenance.content_digest)
        payload = _CiPayload(
            non_authoritative=True,
            consumer=self.consumer,
            renderer=self.renderer,
            source_ref=ArtifactReference(
                artifact_id=artifact.artifact_id,
                content_digest=verified_digest,
            ),
            artifact_type=artifact.artifact_type,
            contract_version=artifact.contract_version,
            project_id=artifact.project_id,
            slice_id=artifact.slice_id,
            slice_instance_id=artifact.slice_instance_id,
            policy=artifact.policy,
            producer=artifact.producer,
            provenance=artifact.provenance,
            source_artifact=artifact,
        )
        return canonical_json_text(payload)


__all__ = ["CiJsonRenderer", "CI_SOURCE_ARTIFACT_KEY"]
