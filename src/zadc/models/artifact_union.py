"""ZadcArtifact: the global, artifact_type-discriminated artifact union (A2B2).

Covers all eight concrete ZADC v0.1 artifacts: :class:`Packet`,
:class:`CompletionReport`, :class:`CertificationManifest`,
:class:`EvidenceArtifact`, :class:`Observation`, :class:`ReviewReport`,
:class:`DecisionRecord`, and :class:`WorkflowBundle`. The union dispatches
on the envelope's ``artifact_type`` field (each concrete model narrows it
to its own ``Literal``), so a payload validates against — and is returned
as — the exact concrete artifact model for its declared type. Unknown,
missing, ``null``, or mismatched ``artifact_type`` values are rejected by
Pydantic's discriminated-union machinery, and body fields belonging to a
different variant are rejected by that variant's own ``extra="forbid"``
configuration.

This module does not implement referential integrity between artifacts
(e.g. verifying that a :class:`~zadc.models.workflow_bundle.WorkflowBundle`
reference actually resolves to a sealed artifact of the claimed type),
policy evaluation, or lifecycle derivation.
"""

from typing import Annotated, Union

from pydantic import Field, TypeAdapter

from zadc.models.certification_manifest import CertificationManifest
from zadc.models.completion_report import CompletionReport
from zadc.models.decision_record import DecisionRecord
from zadc.models.evidence_artifact import EvidenceArtifact
from zadc.models.observation import Observation
from zadc.models.packet import Packet
from zadc.models.review_report import ReviewReport
from zadc.models.workflow_bundle import WorkflowBundle

#: The global discriminated union over every concrete ZADC v0.1 artifact,
#: keyed on the shared envelope field ``artifact_type``.
ZadcArtifact = Annotated[
    Union[
        Packet,
        CompletionReport,
        CertificationManifest,
        EvidenceArtifact,
        Observation,
        ReviewReport,
        DecisionRecord,
        WorkflowBundle,
    ],
    Field(discriminator="artifact_type"),
]

#: The reusable Pydantic adapter backing :func:`validate_artifact` and
#: :func:`validate_artifact_json`. Exposed directly for callers who need
#: adapter-level operations (e.g. ``ZADC_ARTIFACT_ADAPTER.json_schema()``)
#: beyond the two convenience functions below.
ZADC_ARTIFACT_ADAPTER: TypeAdapter[
    Packet
    | CompletionReport
    | CertificationManifest
    | EvidenceArtifact
    | Observation
    | ReviewReport
    | DecisionRecord
    | WorkflowBundle
] = TypeAdapter(ZadcArtifact)


def validate_artifact(value: object) -> ZadcArtifact:
    """Validate a Python mapping against the global :data:`ZadcArtifact` union.

    Dispatches on ``artifact_type`` and returns an instance of the exact
    concrete artifact model class (e.g. a payload with
    ``artifact_type="workflow_bundle"`` returns a
    :class:`~zadc.models.workflow_bundle.WorkflowBundle`, never a bare
    union or base-class instance). Validation is strict, consistent with
    every concrete artifact model's own ``strict=True`` configuration.

    Args:
        value: A Python mapping (e.g. a ``dict`` produced by
            ``json.loads``), or an already-constructed concrete artifact
            model instance.

    Returns:
        The validated, exact concrete artifact model instance.

    Raises:
        pydantic.ValidationError: If ``artifact_type`` is unknown, missing,
            ``null``, or if the payload otherwise fails validation for its
            dispatched variant (including body fields that belong to a
            different artifact variant).
    """
    return ZADC_ARTIFACT_ADAPTER.validate_python(value)


def validate_artifact_json(data: str | bytes | bytearray) -> ZadcArtifact:
    """Validate canonical JSON text or bytes against the global :data:`ZadcArtifact` union.

    Equivalent to ``validate_artifact(json.loads(data))``, but performs
    JSON parsing and validation in a single Pydantic call. See
    :func:`validate_artifact` for dispatch and error behavior.

    Args:
        data: Canonical JSON (or any valid JSON) text or bytes for a single
            ZADC artifact envelope.

    Returns:
        The validated, exact concrete artifact model instance.

    Raises:
        pydantic.ValidationError: See :func:`validate_artifact`.
    """
    return ZADC_ARTIFACT_ADAPTER.validate_json(data)


__all__ = [
    "ZadcArtifact",
    "ZADC_ARTIFACT_ADAPTER",
    "validate_artifact",
    "validate_artifact_json",
]
