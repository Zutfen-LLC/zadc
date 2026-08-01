"""The EvidenceArtifact artifact: metadata and binding for external evidence.

Implements architecture sections 8.9 and 11.3 (``evidence:`` entries). This
model records evidence metadata and binding only — it does not fetch,
retrieve, or independently verify the referenced remote evidence payload
in this slice.
"""

from typing import Literal, Optional

from pydantic import NonNegativeInt

from zadc.models.common import ArtifactEnvelope
from zadc.models.shared import ExactSubject
from zadc.types import ConstrainedText, EvidenceAvailability, GlobalId, MediaType, Sha256Digest


class EvidenceArtifact(ArtifactEnvelope):
    """Metadata and binding for one piece of external verification evidence.

    ``digest`` is the SHA-256 digest of the external evidence payload and
    is semantically and structurally distinct from the inherited
    ``provenance.content_digest``, which seals this artifact's own
    canonical envelope content rather than the referenced external payload.
    """

    artifact_type: Literal["evidence_artifact"]

    verification_run_id: GlobalId
    subject: ExactSubject
    media_type: MediaType
    digest: Sha256Digest
    location: GlobalId
    availability: EvidenceAvailability
    size_bytes: Optional[NonNegativeInt] = None
    description: ConstrainedText


__all__ = ["EvidenceArtifact"]
