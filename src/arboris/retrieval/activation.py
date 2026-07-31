"""Dendritic activation: energy spreading over the typed semantic graph.

Instead of uniform traversal, evidence nodes inject activation energy that
spreads along edges. Edge types modulate propagation (a "causes" edge may
conduct strongly, a "references" edge weakly; "contradicts" can still
conduct — contradiction is evidence too). Activation decays with distance
under a configurable decay function. The resulting activation field decides
where graph expansion looks next.
"""
from __future__ import annotations

import math
from typing import Callable, Mapping

from .interfaces import GraphStore

DecayFn = Callable[[int], float]  # hop distance -> multiplier in [0, 1]


def exponential_decay(rate: float = 0.5) -> DecayFn:
    return lambda hops: rate**hops


def harmonic_decay() -> DecayFn:
    return lambda hops: 1.0 / (1 + hops)


def linear_decay(radius: int = 3) -> DecayFn:
    return lambda hops: max(0.0, 1.0 - hops / radius)


class SpreadingActivation:
    """Reference ActivationEngine.

    edge_weights maps relation type -> conductance (default_weight for
    unlisted types). threshold prunes negligible energy so spread stays
    local. Deterministic: iteration order is sorted, floats are pure
    functions of inputs.
    """

    def __init__(
        self,
        edge_weights: Mapping[str, float] | None = None,
        default_weight: float = 0.5,
        decay: DecayFn | None = None,
        max_hops: int = 3,
        threshold: float = 1e-3,
    ) -> None:
        self.edge_weights = dict(edge_weights or {})
        self.default_weight = default_weight
        self.decay = decay or exponential_decay()
        self.max_hops = max_hops
        self.threshold = threshold

    def spread(self, graph: GraphStore, seeds: Mapping[str, float]) -> dict[str, float]:
        energy: dict[str, float] = {n: e for n, e in seeds.items() if e > 0}
        # frontier carries *raw* energy (seed x edge-weight products, undecayed);
        # recorded activation applies decay(hop distance) to the raw value, so
        # the decay function sees distance, not a compounded per-wave product
        frontier: dict[str, float] = dict(energy)
        for hop in range(1, self.max_hops + 1):
            decay = self.decay(hop)
            if decay <= 0:
                break
            nxt: dict[str, float] = {}
            for node_id in sorted(frontier):
                raw = frontier[node_id]
                for edge in graph.neighbors(node_id):
                    weight = self.edge_weights.get(edge["relation"], self.default_weight)
                    passed_raw = raw * weight
                    if passed_raw * decay < self.threshold:
                        continue
                    other = edge["target"] if edge["source"] == node_id else edge["source"]
                    nxt[other] = max(nxt.get(other, 0.0), passed_raw)
            # a node keeps its highest activation from any wave
            for n, raw in nxt.items():
                activated = raw * decay
                if activated > energy.get(n, 0.0):
                    energy[n] = activated
            frontier = nxt
            if not frontier:
                break
        return energy


def softmax_normalize(activation: Mapping[str, float]) -> dict[str, float]:
    """Optional normalization for comparing activation across hypotheses."""
    if not activation:
        return {}
    mx = max(activation.values())
    exp = {k: math.exp(v - mx) for k, v in activation.items()}
    total = sum(exp.values())
    return {k: v / total for k, v in exp.items()}
