"""Interfaces (structural protocols) for the retrieval subsystem.

Every behavioral component of the pipeline is a Protocol so that any
implementation — a hash-based test double, a dense model, a late-interaction
model, a remote service, an FPGA kernel — is substitutable without touching
the engine. Nothing here names a vendor or model family; concrete adapters
register themselves by name in `registry.py` (e.g. "denseon", "mdenseon",
"lateon", "mlateon" are expected registry names, not imports).

Concurrency contract: retrievers and expanders are async (they may do I/O or
batch model calls and the engine runs many concurrently, synchronizing only
at merge points); pure local computation (embedding lookup, activation
spread, policy checks) is sync.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Protocol, Sequence, runtime_checkable

from .types import (
    Candidate,
    ConvergenceReason,
    Evidence,
    EvidenceGraph,
    Hypothesis,
    Query,
    Scale,
)


# --------------------------------------------------------------------------
# Graph storage
# --------------------------------------------------------------------------
@runtime_checkable
class GraphStore(Protocol):
    """Typed semantic graph access. Read-only from retrieval's perspective:
    the sensory cortex perceives the graph, it does not mutate knowledge."""

    def node(self, node_id: str) -> Mapping[str, Any] | None: ...

    def edge(self, edge_id: str) -> Mapping[str, Any] | None: ...

    def node_ids(self) -> Iterable[str]: ...

    def neighbors(
        self, node_id: str, edge_types: Sequence[str] | None = None
    ) -> Iterable[Mapping[str, Any]]:
        """Edges incident to node_id, optionally filtered by relation type."""
        ...


# --------------------------------------------------------------------------
# Embedding and late interaction providers
# --------------------------------------------------------------------------
@runtime_checkable
class EmbeddingProvider(Protocol):
    """Produces a single vector per text. Used by dense (recall) retrieval."""

    name: str

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


@runtime_checkable
class LateInteractionProvider(Protocol):
    """Produces token-level representations; scoring is query-token x
    item-token interaction (e.g. maxsim). Exposed per Scale so a corpus can
    offer repository/file/function/statement (or document/paragraph/sentence)
    granularities from the same interface."""

    name: str
    scales: tuple[Scale, ...]

    def score(self, query: str, items: Sequence[str]) -> Sequence[float]:
        """Late-interaction relevance of each item text to the query."""
        ...


# --------------------------------------------------------------------------
# Retrievers
# --------------------------------------------------------------------------
@runtime_checkable
class Retriever(Protocol):
    """Anything that turns a Query into candidates. Base contract shared by
    dense, late-interaction, and graph retrievers."""

    name: str

    async def retrieve(self, query: Query, limit: int) -> Sequence[Candidate]: ...


@runtime_checkable
class DenseRetriever(Retriever, Protocol):
    """Stage-1 recall: fast, broad, approximate. Output = candidate ids."""


@runtime_checkable
class LateInteractionRetriever(Protocol):
    """Stage-2 precision: token-level rescoring restricted to candidates."""

    name: str

    async def rerank(
        self, query: Query, candidates: Sequence[Candidate]
    ) -> Sequence[Evidence]: ...


@runtime_checkable
class GraphRetriever(Retriever, Protocol):
    """Retrieval whose index is the graph itself (typed lookups, path
    queries), as opposed to text similarity."""


# --------------------------------------------------------------------------
# Scorers (node / edge / path are distinct: relationships are first-class)
# --------------------------------------------------------------------------
@runtime_checkable
class NodeScorer(Protocol):
    name: str

    def score_nodes(self, query: Query, node_ids: Sequence[str]) -> Sequence[float]: ...


@runtime_checkable
class EdgeScorer(Protocol):
    name: str

    def score_edges(self, query: Query, edge_ids: Sequence[str]) -> Sequence[float]: ...


@runtime_checkable
class PathScorer(Protocol):
    name: str

    def score_paths(
        self, query: Query, paths: Sequence[Sequence[str]]
    ) -> Sequence[float]: ...


# --------------------------------------------------------------------------
# Activation, expansion, convergence
# --------------------------------------------------------------------------
@runtime_checkable
class ActivationEngine(Protocol):
    """Dendritic activation over the graph: energy is injected at evidence
    nodes and spreads along edges, modulated by edge type and decayed by
    distance. Output is a node_id -> activation map."""

    def spread(
        self, graph: GraphStore, seeds: Mapping[str, float]
    ) -> Mapping[str, float]: ...


@runtime_checkable
class ExpansionPolicy(Protocol):
    """Decides which activated neighbors join the working subgraph."""

    def frontier(
        self,
        graph: GraphStore,
        activation: Mapping[str, float],
        visited: set[str],
    ) -> Sequence[str]: ...


@runtime_checkable
class GraphExpander(Protocol):
    """Materializes the frontier: pulls nodes/edges into the evidence graph
    and yields the new frontier as independent retrieval problems."""

    async def expand(
        self,
        graph: GraphStore,
        evidence: EvidenceGraph,
        activation: Mapping[str, float],
        policy: ExpansionPolicy,
        visited: set[str],
    ) -> Sequence[str]: ...


@runtime_checkable
class ConvergencePolicy(Protocol):
    """Stopping is a policy, not a constant. Returns a ConvergenceReason
    when retrieval should stop, else None."""

    name: str

    def check(
        self,
        evidence: EvidenceGraph,
        iteration: int,
        info_gain: float,
        stats: Mapping[str, float],
    ) -> ConvergenceReason | None: ...


# --------------------------------------------------------------------------
# Speculation and merging
# --------------------------------------------------------------------------
@runtime_checkable
class HypothesisManager(Protocol):
    """Turns a query into one or more speculative retrieval lines."""

    def propose(self, query: Query) -> Sequence[Hypothesis]: ...


@runtime_checkable
class EvidenceMerger(Protocol):
    """Merges per-hypothesis evidence graphs after scoring. Merge is the
    only synchronization point in the pipeline."""

    def merge(
        self, results: Mapping[str, tuple[Hypothesis, EvidenceGraph]]
    ) -> EvidenceGraph: ...
