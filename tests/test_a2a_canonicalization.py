"""Each A2A artifact canonicalizes deterministically across construction
order and list-versus-tuple input, per the packet's acceptance criteria."""

import json

import pytest

from tests.a2a_factories import (
    build_certification_manifest,
    build_completion_report,
    build_evidence_artifact,
    build_observation,
    build_packet,
)
from zadc.canonical import canonical_json_text
from zadc.digests import compute_content_digest, seal_artifact

_BUILDERS = [
    build_packet,
    build_completion_report,
    build_certification_manifest,
    build_evidence_artifact,
    build_observation,
]


@pytest.mark.parametrize("builder", _BUILDERS)
def test_reversed_kwarg_construction_order_is_identical(builder: object) -> None:
    """Building from a dict with reversed key insertion order canonicalizes identically."""
    instance = builder()  # type: ignore[operator]
    dumped = instance.model_dump(mode="python", by_alias=True)
    reversed_kwargs = dict(reversed(list(dumped.items())))
    rebuilt = type(instance)(**reversed_kwargs)
    assert canonical_json_text(instance) == canonical_json_text(rebuilt)
    assert compute_content_digest(instance) == compute_content_digest(rebuilt)


@pytest.mark.parametrize("builder", _BUILDERS)
def test_json_roundtrip_with_shuffled_key_order_is_identical(builder: object) -> None:
    """Reloading a JSON dump with reordered dict keys canonicalizes identically."""
    instance = builder()  # type: ignore[operator]
    sealed = seal_artifact(instance)
    canonical_text = canonical_json_text(sealed)
    data = json.loads(canonical_text)
    shuffled = dict(reversed(list(data.items())))
    reloaded = type(sealed).model_validate(shuffled)
    assert canonical_json_text(sealed) == canonical_json_text(reloaded)


@pytest.mark.parametrize("builder", _BUILDERS)
def test_idempotent_canonicalization(builder: object) -> None:
    """Canonicalizing twice in a row produces byte-identical text."""
    instance = builder()  # type: ignore[operator]
    assert canonical_json_text(instance) == canonical_json_text(instance)


class TestListVersusTupleInputParity:
    def test_packet_collection_fields(self) -> None:
        as_lists = build_packet(
            stop_conditions=["a", "b"],
            deliverables=["c"],
            completion_report_requirements=["d"],
        )
        as_tuples = build_packet(
            stop_conditions=("a", "b"),
            deliverables=("c",),
            completion_report_requirements=("d",),
        )
        assert canonical_json_text(as_lists) == canonical_json_text(as_tuples)
        assert compute_content_digest(as_lists) == compute_content_digest(as_tuples)

    def test_completion_report_collection_fields(self) -> None:
        as_lists = build_completion_report(open_issues=[], deviations=[])
        as_tuples = build_completion_report(open_issues=(), deviations=())
        assert canonical_json_text(as_lists) == canonical_json_text(as_tuples)

    def test_certification_manifest_collection_fields(self) -> None:
        as_list = build_certification_manifest()
        lanes_as_tuple = build_certification_manifest(lanes=tuple(as_list.lanes))
        assert canonical_json_text(as_list) == canonical_json_text(lanes_as_tuple)

    def test_observation_evidence_refs(self) -> None:
        as_list = build_observation(evidence_refs=[])
        as_tuple = build_observation(evidence_refs=())
        assert canonical_json_text(as_list) == canonical_json_text(as_tuple)
