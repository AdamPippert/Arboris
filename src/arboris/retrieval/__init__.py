"""Arboris retrieval subsystem — the sensory cortex.

Retrieval produces evidence; reasoning happens afterwards, elsewhere. See
docs/adr/0001-graph-native-retrieval.md for the architectural decision and
docs/rfc/ for the detailed design.

Quick start (dependency-free reference stack):

    from arboris.retrieval import (
        InMemoryGraphStore, RetrievalEngine, Query,
        GraphDenseRetriever, GraphLateInteractionRetriever,
        SpreadingActivation, ActivationFrontier, default_convergence,
    )

    store = InMemoryGraphStore.from_fixture(fixture)
    engine = RetrievalEngine(
        graph=store,
        dense=[GraphDenseRetriever(store)],
        late=GraphLateInteractionRetriever(store),
        activation=SpreadingActivation(),
        expansion=ActivationFrontier(),
        convergence=default_convergence(),
    )
    result = await engine.retrieve(Query(text="..."))
    result.evidence   # EvidenceGraph
    result.trace      # full observability record
"""
from .activation import SpreadingActivation, exponential_decay, harmonic_decay, linear_decay
from .engine import BestScoreMerger, RetrievalEngine, SingleHypothesis
from .graph import InMemoryGraphStore
from .policies import (
    ActivationFrontier,
    AnyOf,
    BudgetExhausted,
    ConfidenceThreshold,
    GraphDiameter,
    MaxIterations,
    MinInformationGain,
    default_convergence,
)
from .providers import (
    GraphDenseRetriever,
    GraphLateInteractionRetriever,
    HashEmbeddingProvider,
    HashLateInteraction,
)
from .types import (
    Candidate,
    ConvergenceReason,
    Evidence,
    EvidenceGraph,
    Hypothesis,
    Query,
    RetrievalHint,
    RetrievalResult,
    RetrievalTrace,
    Scale,
)

__all__ = [
    "ActivationFrontier",
    "AnyOf",
    "BestScoreMerger",
    "BudgetExhausted",
    "Candidate",
    "ConfidenceThreshold",
    "ConvergenceReason",
    "Evidence",
    "EvidenceGraph",
    "GraphDenseRetriever",
    "GraphDiameter",
    "GraphLateInteractionRetriever",
    "HashEmbeddingProvider",
    "HashLateInteraction",
    "Hypothesis",
    "InMemoryGraphStore",
    "MaxIterations",
    "MinInformationGain",
    "Query",
    "RetrievalEngine",
    "RetrievalHint",
    "RetrievalResult",
    "RetrievalTrace",
    "Scale",
    "SingleHypothesis",
    "SpreadingActivation",
    "default_convergence",
    "exponential_decay",
    "harmonic_decay",
    "linear_decay",
]
