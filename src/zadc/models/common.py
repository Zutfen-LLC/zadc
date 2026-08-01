"""Common artifact envelope models for ZADC.

All models are strict (``extra=forbid``), frozen (immutable), and validated
at construction. These implement architecture section 10 (Common artifact
envelope) and the shared types from sections 9 and 11.

FIX2 corrections:
- ``schema`` and ``contract_version`` are now required Literal fields, emitting
  JSON Schema ``const`` entries and ``required`` entries. They have NO defaults.
- ``provenance.parent_artifact_ids`` is required (no default_factory) — root
  artifacts must explicitly supply an empty array/tuple.
- ``created_at`` validates the exact ZADC Timestamp v0.1 grammar via
  ``validate_timestamp`` before parsing, rejecting ``datetime.fromisoformat``
  over-acceptance.
- Independent schema evidence is genuinely independent (Draft202012Validator +
  FormatChecker + explicit pattern).
"""

from datetime import datetime
from typing import Annotated, Literal, Optional

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
    TimestampField,
    coerce_timestamp,
    serialize_timestamp,
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
    - ``parent_artifact_ids``: REQUIRED immutable tuple of parent artifact IDs.
      Accepted as ``list`` or ``tuple`` at construction; internally immutable.
      Root artifacts must explicitly supply an empty array/tuple.
    - ``content_digest``: optional SHA-256 digest of the artifact content.
      May be absent only before sealing.
    """

    parent_artifact_ids: tuple[GlobalId, ...]
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

    FIX2-A: ``schema`` and ``contract_version`` are required Literal fields
    that emit JSON Schema ``const`` entries. They have NO model defaults —
    callers must supply them explicitly (at minimum through the alias or
    field name). The ``model_json_schema(mode='validation')`` output marks
    them as ``required`` with exact ``const`` values.

    FIX2-C: ``created_at`` enforces the exact ZADC Timestamp v0.1 grammar
    via ``validate_timestamp`` (regex fullmatch + calendar/wall-clock/offset
    validation) before parsing to datetime. Normalizes to UTC and serializes
    with uppercase ``Z``.
    """

    schema_uri: Literal[SCHEMA_ID] = Field(alias="schema")  # type: ignore[valid-type]
    contract_version: Literal[CONTRACT_VERSION]  # type: ignore[valid-type]
    artifact_type: ArtifactType
    artifact_id: GlobalId
    created_at: Annotated[datetime, TimestampField]
    producer: ProducerIdentity
    project_id: GlobalId
    slice_id: SliceId
    slice_instance_id: SliceId
    policy: PolicyReference
    provenance: Provenance

    @field_validator("created_at", mode="before")
    @classmethod
    def _validate_created_at(cls, v: object) -> datetime:
        """Accept datetime instances or ZADC Timestamp v0.1 strings.

        FIX2-C: String inputs must match the exact ZADC Timestamp v0.1 grammar
        (YYYY-MM-DDTHH:MM:SS[.ffffff](Z|±HH:MM)). This rejects
        ``datetime.fromisoformat`` over-acceptance examples including:
        space separators, basic forms, week dates, ordinal dates, offsets
        without colon, timezone-free strings, lowercase t/z, >6 fractional
        digits, leap seconds (:60), and -00:00.

        Rejects int, float, Decimal, bool, bytes, naive datetime, and date.

        Delegates to the shared ``coerce_timestamp`` helper (A2A-02) so
        nested artifact timestamps enforce byte-identical behavior; this
        delegation is a pure refactor and does not alter the validation
        outcome for any input.
        """
        return coerce_timestamp(v)

    @field_serializer("created_at")
    def _serialize_created_at(self, v: datetime) -> str:
        """Serialize datetime as UTC RFC 3339 with uppercase Z."""
        return serialize_timestamp(v)


__all__ = [
    "ArtifactEnvelope",
    "PolicyReference",
    "ProducerIdentity",
    "Provenance",
]
