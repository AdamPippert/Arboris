from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from arboris.schemas import GraphNode, ProvenanceRecord, canonical_json


def test_schema_round_trip_is_deterministic() -> None:
    node = GraphNode(id="node-1", type="Node", attributes={"b": 2, "a": 1})
    assert GraphNode.model_validate_json(node.model_dump_json()) == node
    assert canonical_json(node) == canonical_json(node)


def test_invalid_confidence_and_interval_are_rejected() -> None:
    with pytest.raises(ValidationError):
        GraphNode(id="n", type="Node", confidence=1.1)
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        GraphNode(id="n", type="Node", valid_from=now, valid_to=now - timedelta(seconds=1))


def test_provenance_is_content_addressed() -> None:
    a = ProvenanceRecord.for_content(b"same", source_type="simulation")
    b = ProvenanceRecord.for_content(b"same", source_type="simulation")
    c = ProvenanceRecord.for_content(b"different", source_type="simulation")
    assert a.source_hash == b.source_hash
    assert a.provenance_id == b.provenance_id
    assert a.source_hash != c.source_hash
