"""Common artifact envelope models for ZADC.

All models are strict (``extra=forbid``), frozen (immutable), and validated
at construction. These implement architecture section 10 (Common artifact
envelope) and the shared types from sections 9 and 11.

No status/authority field is declared — the envelope carries no
authorization, verification, approval, merge-worthiness, or merge claim.
That is an intentional design constraint for v0.1.
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
    Sha256Digest,
    StableId,
)

# Sentinel value used to distinguish "not provided" from explicit ``None``
# for the optional content_digest field. Using a private sentinel ensures
# that callers who pass ``content_digest=None`` explicitly are treated the
# same as those who omit the field entirely.
_UNSET: object = object()


class _ZadcModel(BaseModel):
    """Base configuration for all ZADC models.

    - ``frozen=True``   — instances are immutable.
    - ``extra=forbid``  — unknown fields raise ``ValidationError``.
    - ``populate_by_name=True`` — accepts both field name and alias.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
    )


class ProducerIdentity(_ZadcModel):
    """Identity of the actor that produced an artifact.

    Fields (architecture section 10, ``producer``):
    - ``actor_type``: human, agent, ci, validator, service.
    - ``actor_id``: stable identifier for the actor.
    - ``run_id``: optional run/execution identifier.
    - ``model``: optional model identifier (for agent producers).
    - ``provider``: optional provider/service identifier.
    """

    actor_type: ActorType
    actor_id: StableId
    run_id: Optional[StableId] = None
    model: Optional[str] = None
    provider: Optional[str] = None


class PolicyReference(_ZadcModel):
    """Reference to the policy governing an artifact.

    Fields (architecture section 10, ``policy``):
    - ``policy_id``: the policy identifier (e.g. ``zutfen:zadc-policy:standard@0.1.0``).
    - ``policy_source_sha``: the trusted commit SHA the policy was loaded from.
    - ``policy_digest``: the SHA-256 digest of the policy content.
    """

    policy_id: StableId
    policy_source_sha: GitSha
    policy_digest: Sha256Digest


class Provenance(_ZadcModel):
    """Provenance chain for an artifact.

    Fields (architecture section 10, ``provenance``):
    - ``parent_artifact_ids``: list of parent artifact IDs (empty list for roots).
    - ``content_digest``: optional SHA-256 digest of the artifact content.
      May be absent only before sealing.
    """

    parent_artifact_ids: list[StableId] = Field(default_factory=list)
    content_digest: Optional[Sha256Digest] = None


class ArtifactEnvelope(_ZadcModel):
    """The common envelope shared by all ZADC artifacts.

    Fields exactly follow architecture section 10. The envelope carries
    structural identity and provenance but NO status or authority field.

    ``created_at`` MUST be timezone-aware. Any accepted timezone offset
    is normalized to UTC. Serialization uses uppercase ``Z`` for the
    zero-offset designator.

    ``content_digest`` may be absent (``None``) only before sealing.
    After sealing via :func:`zadc.digests.seal_artifact`, the digest is
    populated and MUST match when verified.
    """

    schema_uri: str = Field(default=SCHEMA_ID, alias="schema")
    contract_version: str = Field(default=CONTRACT_VERSION)
    artifact_type: ArtifactType
    artifact_id: StableId
    created_at: datetime
    producer: ProducerIdentity
    project_id: StableId
    slice_id: StableId
    slice_instance_id: StableId
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

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        # Normalize to UTC.
        return v.astimezone(UTC)

    @field_serializer("created_at")
    def _serialize_created_at(self, v: datetime) -> str:
        """Serialize datetime as UTC RFC 3339 with uppercase Z.

        Fractional seconds are preserved if present in the original value.
        The output always uses ``Z`` for the UTC offset designator.
        """
        utc_dt = v.astimezone(UTC)
        # isoformat() on a UTC-normalized datetime ends with "+00:00";
        # replace it with the canonical uppercase Z designator.
        return utc_dt.isoformat().replace("+00:00", "Z")

    def model_dump_json_compatible(self) -> dict[str, object]:
        """Dump the model as a JSON-compatible dict with aliases.

        This is used by the canonical serializer. All datetime values
        are serialized as UTC RFC 3339 strings with uppercase Z.
        ``None`` values are preserved as ``None`` (serialized as ``null``
        by the canonical JSON encoder).
        """
        return self.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=False,
        )


__all__ = [
    "ArtifactEnvelope",
    "PolicyReference",
    "ProducerIdentity",
    "Provenance",
]
