"""Common artifact envelope models for ZADC.

All models are strict (``extra=forbid``), frozen (immutable), and validated
at construction. These implement architecture section 10 (Common artifact
envelope) and the shared types from sections 9 and 11.

FIX1-B corrections:
- ``model_config`` uses ``strict=True`` to reject unintended Python-mode
  coercions (int/float/Decimal/bool timestamps, non-string IDs/SHAs).
- ``provenance.parent_artifact_ids`` uses an immutable tuple internally,
  accepted as list or tuple at validation boundaries.
- ``created_at`` uses a ``BeforeValidator`` that admits only ``datetime``
  instances or RFC 3339 strings (from decoded JSON).
- ``seal_artifact`` uses validated reconstruction (``model_validate``) not
  unvalidated ``model_copy(update=...)``.
"""

from datetime import UTC, datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

from zadc.types import (
    CONTRACT_VERSION,
    SCHEMA_ID,
    ActorType,
    ArtifactType,
    GitSha,
    GlobalId,
    Sha256Digest,
    SliceId,
)


class _ZadcModel(BaseModel):
    """Base configuration for all ZADC models.

    - ``frozen=True``  — instances are immutable.
    - ``strict=True``  — reject unintended coercions.
    - ``extra=forbid`` — unknown fields raise ``ValidationError``.
    - ``populate_by_name=True`` — accepts both field name and alias.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        populate_by_name=True,
    )


class ProducerIdentity(_ZadcModel):
    """Identity of the actor that produced an artifact.

    Fields (architecture section 10, ``producer``):
    - ``actor_type``: human, agent, ci, validator, service.
    - ``actor_id``: URI-shaped global identifier for the actor.
    - ``run_id``: optional run/execution identifier.
    - ``model``: optional model identifier (for agent producers).
    - ``provider``: optional provider/service identifier.
    """

    actor_type: ActorType
    actor_id: GlobalId
    run_id: Optional[GlobalId] = None
    model: Optional[str] = None
    provider: Optional[str] = None


class PolicyReference(_ZadcModel):
    """Reference to the policy governing an artifact.

    Fields (architecture section 10, ``policy``):
    - ``policy_id``: the policy identifier (e.g. ``zutfen:zadc-policy:standard@0.1.0``).
    - ``policy_source_sha``: the trusted commit SHA the policy was loaded from.
    - ``policy_digest``: the SHA-256 digest of the policy content.
    """

    policy_id: GlobalId
    policy_source_sha: GitSha
    policy_digest: Sha256Digest


class Provenance(_ZadcModel):
    """Provenance chain for an artifact.

    Fields (architecture section 10, ``provenance``):
    - ``parent_artifact_ids``: immutable tuple of parent artifact IDs.
      Accepted as ``list`` or ``tuple`` at construction; internally immutable.
    - ``content_digest``: optional SHA-256 digest of the artifact content.
      May be absent only before sealing.
    """

    parent_artifact_ids: tuple[GlobalId, ...] = Field(default_factory=tuple)
    content_digest: Optional[Sha256Digest] = None

    @field_validator("parent_artifact_ids", mode="before")
    @classmethod
    def _accept_list_or_tuple(cls, v: object) -> tuple[object, ...]:
        """Accept list or tuple input and normalize to tuple."""
        if isinstance(v, list):
            return tuple(v)
        return v  # type: ignore[return-value]


class ArtifactEnvelope(_ZadcModel):
    """The common envelope shared by all ZADC artifacts.

    Fields exactly follow architecture section 10. The envelope carries
    structural identity and provenance but NO status or authority field.

    ``created_at`` MUST be timezone-aware. It accepts a ``datetime``
    instance or an RFC 3339 string (from decoded JSON). Any accepted
    timezone offset is normalized to UTC. Serialization uses uppercase
    ``Z`` for the zero-offset designator.
    """

    schema_uri: str = Field(default=SCHEMA_ID, alias="schema")
    contract_version: str = Field(default=CONTRACT_VERSION)
    artifact_type: ArtifactType
    artifact_id: GlobalId
    created_at: datetime
    producer: ProducerIdentity
    project_id: GlobalId
    slice_id: SliceId
    slice_instance_id: SliceId
    policy: PolicyReference
    provenance: Provenance

    @field_validator("contract_version")
    @classmethod
    def _validate_contract_version(cls, v: str) -> str:
        if v != CONTRACT_VERSION:
            raise ValueError(f"contract_version must be exactly '{CONTRACT_VERSION}'")
        return v

    @field_validator("schema_uri")
    @classmethod
    def _validate_schema(cls, v: str) -> str:
        if v != SCHEMA_ID:
            raise ValueError(f"schema must be exactly '{SCHEMA_ID}'")
        return v

    @field_validator("created_at", mode="before")
    @classmethod
    def _validate_created_at(cls, v: object) -> datetime:
        """Accept only datetime instances or RFC 3339 strings.

        Rejects int, float, Decimal, bool, bytes, naive datetime, and date.
        """
        if isinstance(v, datetime):
            if v.tzinfo is None:
                raise ValueError("created_at must be timezone-aware")
            return v.astimezone(UTC)
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"created_at must be a valid RFC 3339 string: {v!r}") from exc
            if dt.tzinfo is None:
                raise ValueError("created_at string must include a timezone offset")
            return dt.astimezone(UTC)
        # Reject all other types — no coercion of int/float/bool/etc.
        raise TypeError(
            f"created_at must be a timezone-aware datetime or RFC 3339 string, "
            f"not {type(v).__name__}"
        )

    @field_serializer("created_at")
    def _serialize_created_at(self, v: datetime) -> str:
        """Serialize datetime as UTC RFC 3339 with uppercase Z."""
        utc_dt = v.astimezone(UTC)
        return utc_dt.isoformat().replace("+00:00", "Z")


__all__ = [
    "ArtifactEnvelope",
    "PolicyReference",
    "ProducerIdentity",
    "Provenance",
]
