"""The Observation artifact: a timestamped statement from a named source.

Implements architecture section 8.14. An observation is a timestamped
record of what a named source reported, not automatically a timeless fact
(architecture section 5.4, "live systems remain authoritative"). This
model does not compute ``STALE`` status or query the source; it only
records what was captured, when, and by whom.
"""

from typing import Annotated, Literal, Optional

from pydantic import BeforeValidator, PositiveInt, model_validator

from zadc.models.common import ArtifactEnvelope
from zadc.models.shared import EvidenceReference, ObservationSource
from zadc.types import ConstrainedText, EpistemicStatus, GlobalId, Timestamp, coerce_tuple


class Observation(ArtifactEnvelope):
    """A timestamped statement derived from a named source (architecture 8.14)."""

    artifact_type: Literal["observation"]

    subject_id: GlobalId
    source: ObservationSource
    observed_at: Timestamp
    statement: ConstrainedText
    epistemic_status: EpistemicStatus
    evidence_refs: Annotated[tuple[EvidenceReference, ...], BeforeValidator(coerce_tuple)]
    freshness_seconds: Optional[PositiveInt] = None
    expires_at: Optional[Timestamp] = None

    @model_validator(mode="after")
    def _check_observation_invariants(self) -> "Observation":
        if self.expires_at is not None and self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be later than observed_at")
        return self


__all__ = ["Observation"]
