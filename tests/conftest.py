"""Shared test fixtures for ZADC A1 behavioral proofs and unit tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from zadc import ArtifactEnvelope, PolicyReference, ProducerIdentity, Provenance


@pytest.fixture
def sample_producer() -> ProducerIdentity:
    """A minimal valid ProducerIdentity."""
    return ProducerIdentity(
        actor_type="human",
        actor_id="zutfen:human:eric",
    )


@pytest.fixture
def sample_producer_full() -> ProducerIdentity:
    """A fully-specified ProducerIdentity."""
    return ProducerIdentity(
        actor_type="agent",
        actor_id="zutfen:agent:hermes",
        run_id="urn:uuid:00000000-0000-0000-0000-000000000010",
        model="glm-5.2",
        provider="zai",
    )


@pytest.fixture
def sample_policy() -> PolicyReference:
    """A valid PolicyReference."""
    return PolicyReference(
        policy_id="zutfen:zadc-policy:standard@0.1.0",
        policy_source_sha="a" * 40,
        policy_digest="sha256:" + "b" * 64,
    )


@pytest.fixture
def sample_provenance_empty() -> Provenance:
    """A Provenance with no parents and no digest (unsealed)."""
    return Provenance(parent_artifact_ids=[])


@pytest.fixture
def sample_envelope(
    sample_producer: ProducerIdentity,
    sample_policy: PolicyReference,
    sample_provenance_empty: Provenance,
) -> ArtifactEnvelope:
    """A minimal valid unsealed ArtifactEnvelope."""
    return ArtifactEnvelope(
        artifact_type="packet",
        artifact_id="urn:uuid:00000000-0000-0000-0000-000000000001",
        created_at=datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC),
        producer=sample_producer,
        project_id="zutfen:project:zadc",
        slice_id="ZADC-001A",
        slice_instance_id="ZADC-001A1",
        policy=sample_policy,
        provenance=sample_provenance_empty,
    )
