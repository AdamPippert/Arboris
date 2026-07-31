"""The retrieval engine: async orchestration of the evidence pipeline.

    Query -> [hypotheses in parallel] ->
        loop until convergence:
            stage 1  dense recall            (parallel across frontier queries)
            stage 2  late-interaction rerank (candidates only)
            stage 3  dendritic activation + graph expansion
            stage 4  frontier nodes become independent retrieval problems
        -> merge hypotheses (only synchronization point) -> EvidenceGraph

The engine holds NO model logic and NO reasoning logic. It composes the
protocol implementations it is given, records everything in the trace, and
returns evidence. What the evidence *means* is someone else's job — that
separation is the architecture.
"""
from __future__ import annotations

import asyncio
from typing import Mapping, Sequence

from .interfaces import (
    ActivationEngine,
    ConvergencePolicy,
    DenseRetriever,
    EvidenceMerger,
    ExpansionPolicy,
    GraphStore,
    HypothesisManager,
    LateInteractionRetriever,
)
from .types import (
    ConvergenceReason,
    Evidence,
    EvidenceGraph,
    Hypothesis,
    Query,
    RetrievalResult,
    RetrievalTrace,
)


class SingleHypothesis:
    """Default HypothesisManager: the query itself is the only hypothesis.
    Speculative callers supply their own manager (or SGJM-derived hints)."""

    def propose(self, query: Query) -> list[Hypothesis]:
        return [Hypothesis(hypothesis_id="h0", query=query)]


class BestScoreMerger:
    """Default EvidenceMerger: union of hypothesis graphs, best score per
    item wins, weighted by hypothesis prior. Merging happens strictly after
    scoring — no hypothesis is collapsed early."""

    def merge(self, results: Mapping[str, tuple[Hypothesis, EvidenceGraph]]) -> EvidenceGraph:
        merged = EvidenceGraph()
        for _, (hyp, graph) in sorted(results.items()):
            merged.nodes.update(graph.nodes)
            merged.edges.update(graph.edges)
            for ev in graph.scores.values():
                weighted = Evidence(
                    item_id=ev.item_id,
                    kind=ev.kind,
                    scale=ev.scale,
                    score=ev.score * hyp.prior,
                    channels={**ev.channels, "hypothesis": hyp.prior},
                    payload=ev.payload,
                )
                merged.merge_evidence(weighted)
        return merged


class RetrievalEngine:
    def __init__(
        self,
        graph: GraphStore,
        dense: Sequence[DenseRetriever],
        late: LateInteractionRetriever,
        activation: ActivationEngine,
        expansion: ExpansionPolicy,
        convergence: ConvergencePolicy,
        hypotheses: HypothesisManager | None = None,
        merger: EvidenceMerger | None = None,
        recall_limit: int = 16,
        min_evidence_score: float = 0.05,
    ) -> None:
        self.graph = graph
        self.dense = list(dense)
        self.late = late
        self.activation = activation
        self.expansion = expansion
        self.convergence = convergence
        self.hypotheses = hypotheses or SingleHypothesis()
        self.merger = merger or BestScoreMerger()
        self.recall_limit = recall_limit
        self.min_evidence_score = min_evidence_score

    # ------------------------------------------------------------------
    async def retrieve(self, query: Query) -> RetrievalResult:
        trace = RetrievalTrace()
        hyps = list(self.hypotheses.propose(query))
        trace.emit("hypotheses", count=len(hyps), ids=[h.hypothesis_id for h in hyps])

        per_hyp = await asyncio.gather(*(self._run_hypothesis(h, trace) for h in hyps))
        results = {h.hypothesis_id: (h, g) for h, g in per_hyp}

        merged = self.merger.merge(results)
        trace.emit(
            "merge",
            hypotheses=len(results),
            merged_nodes=len(merged.nodes),
            merged_edges=len(merged.edges),
            total_mass=round(merged.total_mass, 4),
        )
        return RetrievalResult(
            query=query,
            evidence=merged,
            trace=trace,
            hypotheses={hid: g for hid, (_, g) in results.items()},
        )

    # ------------------------------------------------------------------
    async def _run_hypothesis(
        self, hyp: Hypothesis, trace: RetrievalTrace
    ) -> tuple[Hypothesis, EvidenceGraph]:
        evidence = EvidenceGraph()
        visited: set[str] = set()
        stats: dict[str, float] = {"node_visits": 0.0}
        frontier_queries: list[Query] = [hyp.query]
        # SGJM (or any caller) hints seed the frontier as extra queries —
        # hints bias where retrieval looks; they never bypass scoring
        for hint in hyp.query.hints:
            text = hint.payload.get("text")
            if text:
                frontier_queries.append(Query(text=str(text), scales=hyp.query.scales))
        iteration = 0
        reason: ConvergenceReason | None = None

        while reason is None:
            prev_mass = evidence.total_mass

            # stage 1: dense recall — all retrievers x all frontier queries, parallel
            recall_tasks = [
                retriever.retrieve(q, self.recall_limit)
                for q in frontier_queries
                for retriever in self.dense
            ]
            candidate_lists = await asyncio.gather(*recall_tasks)
            seen: dict[str, object] = {}
            for cands in candidate_lists:
                for c in cands:
                    if c.item_id not in seen or c.score > seen[c.item_id].score:  # type: ignore[union-attr]
                        seen[c.item_id] = c
            candidates = [seen[k] for k in sorted(seen)]
            trace.emit(
                "dense_recall",
                hypothesis=hyp.hypothesis_id,
                iteration=iteration,
                queries=len(frontier_queries),
                candidates=len(candidates),
            )

            # stage 2: late interaction on candidates only
            scored = await self.late.rerank(hyp.query, candidates)  # type: ignore[arg-type]
            accepted = [ev for ev in scored if ev.score >= self.min_evidence_score]
            for ev in accepted:
                if evidence.merge_evidence(ev):
                    node = self.graph.node(ev.item_id)
                    if node is not None:
                        evidence.nodes[ev.item_id] = node
            trace.emit(
                "late_interaction",
                hypothesis=hyp.hypothesis_id,
                iteration=iteration,
                scored=len(scored),
                accepted=len(accepted),
            )

            # stage 3: dendritic activation from current evidence, then expansion
            seeds = {ev.item_id: ev.score for ev in evidence.scores.values() if ev.kind == "node"}
            field = self.activation.spread(self.graph, seeds)
            visited.update(seeds)
            frontier = list(self.expansion.frontier(self.graph, field, visited))
            for node_id in frontier:
                visited.add(node_id)
                stats["node_visits"] += 1
                node = self.graph.node(node_id)
                if node is not None:
                    evidence.nodes[node_id] = node
            # close the subgraph: any edge whose both endpoints are in evidence
            # belongs to the evidence graph, whether its nodes arrived via
            # late-interaction acceptance or frontier expansion
            for node_id in sorted(evidence.nodes):
                for edge in self.graph.neighbors(node_id):
                    if edge["source"] in evidence.nodes and edge["target"] in evidence.nodes:
                        evidence.edges[edge["id"]] = edge
            trace.emit(
                "activation_expansion",
                hypothesis=hyp.hypothesis_id,
                iteration=iteration,
                activated=len(field),
                frontier=list(frontier),
                evidence_nodes=len(evidence.nodes),
                evidence_edges=len(evidence.edges),
            )

            # stage 4: each frontier node becomes its own retrieval problem
            frontier_queries = [
                Query(text=self._node_query_text(node_id), scales=hyp.query.scales)
                for node_id in frontier
            ]

            info_gain = evidence.total_mass - prev_mass
            iteration += 1
            reason = self.convergence.check(evidence, iteration, info_gain, stats)
            if reason is None and not frontier_queries:
                reason = ConvergenceReason("frontier_exhausted", "no expandable frontier")
        trace.emit(
            "convergence",
            hypothesis=hyp.hypothesis_id,
            policy=reason.policy,
            detail=reason.detail,
            iterations=iteration,
        )
        trace.convergence = reason
        return hyp, evidence

    def _node_query_text(self, node_id: str) -> str:
        node = self.graph.node(node_id) or {}
        return str(node.get("name") or node.get("description") or node_id)
