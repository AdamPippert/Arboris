"""Expansion and convergence policies.

Retrieval stops and spreads by policy, not by constants. Policies are small,
pure, composable objects; the engine treats them as opaque. "Top-K" is just
one degenerate convergence policy — the default posture is: continue until
the evidence graph is coherent and further work stops paying.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from .interfaces import GraphStore
from .types import ConvergenceReason, EvidenceGraph


# --------------------------------------------------------------------------
# Expansion
# --------------------------------------------------------------------------
class ActivationFrontier:
    """Reference ExpansionPolicy: expand activated, unvisited nodes above a
    threshold, best-first, optionally restricted to edge types (typed edges,
    ontology links, temporal/causal/semantic neighbors are all just relation
    types on the graph — the policy filters, the graph provides)."""

    def __init__(
        self,
        min_activation: float = 0.05,
        max_frontier: int = 8,
        edge_types: Sequence[str] | None = None,
    ) -> None:
        self.min_activation = min_activation
        self.max_frontier = max_frontier
        self.edge_types = tuple(edge_types) if edge_types is not None else None

    def frontier(
        self,
        graph: GraphStore,
        activation: Mapping[str, float],
        visited: set[str],
    ) -> list[str]:
        eligible = [
            (energy, node_id)
            for node_id, energy in activation.items()
            if node_id not in visited and energy >= self.min_activation
        ]
        eligible.sort(key=lambda t: (-t[0], t[1]))  # energy desc, id asc: deterministic
        return [node_id for _, node_id in eligible[: self.max_frontier]]


# --------------------------------------------------------------------------
# Convergence
# --------------------------------------------------------------------------
class MaxIterations:
    name = "max_iterations"

    def __init__(self, limit: int = 4) -> None:
        self.limit = limit

    def check(self, evidence: EvidenceGraph, iteration: int, info_gain: float, stats: Mapping[str, float]):
        if iteration >= self.limit:
            return ConvergenceReason(self.name, f"iteration {iteration} >= {self.limit}")
        return None


class MinInformationGain:
    """Stop when an iteration adds too little new evidence mass."""

    name = "min_information_gain"

    def __init__(self, min_gain: float = 0.05) -> None:
        self.min_gain = min_gain

    def check(self, evidence: EvidenceGraph, iteration: int, info_gain: float, stats: Mapping[str, float]):
        if iteration > 0 and info_gain < self.min_gain:
            return ConvergenceReason(self.name, f"gain {info_gain:.4f} < {self.min_gain}")
        return None


class ConfidenceThreshold:
    """Stop once enough high-confidence evidence has accumulated."""

    name = "confidence_threshold"

    def __init__(self, threshold: float = 0.9, count: int = 3) -> None:
        self.threshold = threshold
        self.count = count

    def check(self, evidence: EvidenceGraph, iteration: int, info_gain: float, stats: Mapping[str, float]):
        strong = sum(1 for e in evidence.scores.values() if e.score >= self.threshold)
        if strong >= self.count:
            return ConvergenceReason(self.name, f"{strong} items >= {self.threshold}")
        return None


class BudgetExhausted:
    """Stop on any tracked budget (tokens, node visits, wall-time supplied
    via stats by the engine)."""

    name = "budget_exhausted"

    def __init__(self, budget_key: str, limit: float) -> None:
        self.budget_key = budget_key
        self.limit = limit

    def check(self, evidence: EvidenceGraph, iteration: int, info_gain: float, stats: Mapping[str, float]):
        spent = stats.get(self.budget_key, 0.0)
        if spent >= self.limit:
            return ConvergenceReason(self.name, f"{self.budget_key} {spent} >= {self.limit}")
        return None


class GraphDiameter:
    """Stop when the evidence graph has grown to a bounded size."""

    name = "graph_diameter"

    def __init__(self, max_nodes: int = 64) -> None:
        self.max_nodes = max_nodes

    def check(self, evidence: EvidenceGraph, iteration: int, info_gain: float, stats: Mapping[str, float]):
        if len(evidence.nodes) >= self.max_nodes:
            return ConvergenceReason(self.name, f"{len(evidence.nodes)} nodes >= {self.max_nodes}")
        return None


class AnyOf:
    """First policy to fire wins. Policies are checked in order, so put the
    hard safety limits (budget, iterations) last to make soft criteria the
    preferred stop reason in traces."""

    name = "any_of"

    def __init__(self, *policies) -> None:
        self.policies = policies

    def check(self, evidence: EvidenceGraph, iteration: int, info_gain: float, stats: Mapping[str, float]):
        for policy in self.policies:
            reason = policy.check(evidence, iteration, info_gain, stats)
            if reason is not None:
                return reason
        return None


def default_convergence() -> AnyOf:
    return AnyOf(
        ConfidenceThreshold(),
        MinInformationGain(),
        GraphDiameter(),
        MaxIterations(),
    )
