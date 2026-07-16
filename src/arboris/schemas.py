"""Canonical, provenance-aware graph records."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def new_id(prefix: str) -> str:
    """Return a time-sortable UUID-like identifier.

    Python 3.12 does not expose UUIDv7, so UUID1 supplies sortable time bits while
    callers receive an opaque identifier. This can be replaced without schema drift.
    """
    return f"{prefix}_{uuid.uuid1()}"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GraphNode(Record):
    id: str
    type: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_interval(self) -> GraphNode:
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not precede valid_from")
        return self


class GraphEdge(Record):
    id: str
    subject_id: str
    predicate: str
    object_id: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance_ids: list[str] = Field(default_factory=list)


class StateGraph(Record):
    graph_id: str
    timestamp: datetime | None = None
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    ontology_version: str
    provenance_ids: list[str] = Field(default_factory=list)


class Intervention(Record):
    intervention_id: str
    action_type: str
    actor_id: str | None = None
    target_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None


class Observation(Record):
    observation_id: str
    observed_ids: list[str]
    attributes: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance_ids: list[str] = Field(default_factory=list)


class TransitionEpisode(Record):
    episode_id: str
    state_before: StateGraph
    intervention: Intervention | None
    state_after: StateGraph
    observations: list[Observation] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance_ids: list[str] = Field(default_factory=list)
    domain: str
    persona_tags: list[str] = Field(default_factory=list)


class PredictionBranch(Record):
    branch_id: str
    predicted_state: StateGraph
    probability: float | None = Field(default=None, ge=0.0, le=1.0)
    energy: float | None = None
    uncertainty: float = Field(ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list)
    supporting_pack_ids: list[str] = Field(default_factory=list)
    constraint_violations: list[str] = Field(default_factory=list)
    expected_reward: float | None = None
    parent_branch_id: str | None = None


class ProvenanceRecord(Record):
    provenance_id: str
    source_uri: str | None = None
    source_hash: str
    source_type: str
    license: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    extractor: str | None = None
    generator: str | None = None
    transformation_chain: list[str] = Field(default_factory=list)
    validation_results: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @classmethod
    def for_content(cls, content: bytes, **kwargs: Any) -> ProvenanceRecord:
        digest = hashlib.sha256(content).hexdigest()
        return cls(provenance_id=f"prov_sha256_{digest[:24]}", source_hash=digest, **kwargs)


class GraphDelta(Record):
    added_nodes: list[GraphNode] = Field(default_factory=list)
    removed_node_ids: list[str] = Field(default_factory=list)
    changed_nodes: list[GraphNode] = Field(default_factory=list)
    added_edges: list[GraphEdge] = Field(default_factory=list)
    removed_edge_ids: list[str] = Field(default_factory=list)


class ValidationIssue(Record):
    code: str
    severity: Literal["error", "warning"]
    message: str
    affected_ids: list[str] = Field(default_factory=list)
    suggested_repair: str | None = None


def canonical_json(record: BaseModel) -> bytes:
    return json.dumps(
        record.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
