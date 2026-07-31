"""Core data model for the Arboris retrieval subsystem.

Retrieval is Arboris's sensory cortex: it perceives and assembles *evidence*;
reasoning happens elsewhere, afterwards. Everything in this module is inert
data — no behavior, no model calls — so that every stage of the pipeline can
be observed, serialized, replayed, and tested in isolation.
"""
from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Mapping


class Scale(enum.Enum):
    """Granularities at which evidence can be retrieved and scored.

    One enum spans both document-shaped and code-shaped corpora; a corpus
    exposes whichever scales it has. The engine fuses across scales rather
    than privileging one.
    """

    REPOSITORY = "repository"
    DOCUMENT = "document"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    FILE = "file"
    OBJECT = "object"
    FUNCTION = "function"
    BASIC_BLOCK = "basic_block"
    STATEMENT = "statement"
    NODE = "node"
    EDGE = "edge"
    PATH = "path"


@dataclass(frozen=True)
class RetrievalHint:
    """A prediction from outside the retrieval system (typically the SGJM,
    Arboris's predictive world model) suggesting where evidence may be.

    Hints bias retrieval; they never bypass scoring. kind is open-ended;
    conventional kinds: "missing_evidence", "expansion", "hidden_relation",
    "future_state".
    """

    kind: str
    payload: Mapping[str, Any]
    weight: float = 1.0
    source: str = "unknown"


@dataclass(frozen=True)
class Query:
    """An evidence request. Immutable so hypotheses can share it safely."""

    text: str
    scales: tuple[Scale, ...] = (Scale.NODE,)
    hints: tuple[RetrievalHint, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Candidate:
    """A recall-stage result: cheap to produce, unranked for precision."""

    item_id: str
    scale: Scale
    score: float
    provider: str


@dataclass(frozen=True)
class Evidence:
    """A precision-stage result attached to a graph item.

    kind is "node", "edge", or "path". channels preserves each scorer's
    contribution so merge decisions stay auditable.
    """

    item_id: str
    kind: str
    scale: Scale
    score: float
    channels: Mapping[str, float] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceGraph:
    """The retrieval product: the smallest coherent subgraph of evidence.

    node/edge payloads mirror the graph store's records; scores index by
    item id. This is what gets handed to reasoning — never raw hit lists.
    """

    nodes: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    edges: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    scores: dict[str, Evidence] = field(default_factory=dict)

    def merge_evidence(self, ev: Evidence) -> bool:
        """Keep the best score per item; return True if this was new/better."""
        cur = self.scores.get(ev.item_id)
        if cur is None or ev.score > cur.score:
            self.scores[ev.item_id] = ev
            return True
        return False

    @property
    def total_mass(self) -> float:
        return sum(e.score for e in self.scores.values())


@dataclass(frozen=True)
class Hypothesis:
    """One speculative line of retrieval. Hypotheses run independently and
    are merged only after scoring — never forced to converge early."""

    hypothesis_id: str
    query: Query
    prior: float = 1.0


@dataclass(frozen=True)
class ConvergenceReason:
    policy: str
    detail: str


@dataclass
class TraceEvent:
    """One observable step. stage names the pipeline stage; data is
    stage-specific but always JSON-serializable."""

    stage: str
    data: Mapping[str, Any]
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class RetrievalTrace:
    """Complete observability record for one retrieval run: activation
    traces, expansions, scores, merge decisions, convergence — enough to
    visualize or replay the run without re-executing models."""

    events: list[TraceEvent] = field(default_factory=list)
    convergence: ConvergenceReason | None = None

    def emit(self, stage: str, **data: Any) -> None:
        self.events.append(TraceEvent(stage=stage, data=data))

    def stages(self) -> list[str]:
        return [e.stage for e in self.events]


@dataclass
class RetrievalResult:
    """EvidenceGraph + full trace. The trace is not optional: retrieval
    without observability is not debuggable, and this subsystem is designed
    to be inspected."""

    query: Query
    evidence: EvidenceGraph
    trace: RetrievalTrace
    hypotheses: dict[str, EvidenceGraph] = field(default_factory=dict)
