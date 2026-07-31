from arboris.retrieval import (
    AnyOf,
    BudgetExhausted,
    ConfidenceThreshold,
    Evidence,
    EvidenceGraph,
    GraphDiameter,
    MaxIterations,
    MinInformationGain,
    Scale,
)


def graph_with(scores):
    g = EvidenceGraph()
    for i, s in enumerate(scores):
        g.merge_evidence(Evidence(item_id=f"n{i}", kind="node", scale=Scale.NODE, score=s))
        g.nodes[f"n{i}"] = {"id": f"n{i}"}
    return g


def test_max_iterations():
    p = MaxIterations(limit=3)
    assert p.check(EvidenceGraph(), 2, 1.0, {}) is None
    reason = p.check(EvidenceGraph(), 3, 1.0, {})
    assert reason is not None and reason.policy == "max_iterations"


def test_min_information_gain_ignores_first_iteration():
    p = MinInformationGain(min_gain=0.5)
    assert p.check(EvidenceGraph(), 0, 0.0, {}) is None
    assert p.check(EvidenceGraph(), 2, 0.1, {}) is not None


def test_confidence_threshold_counts_strong_evidence():
    p = ConfidenceThreshold(threshold=0.9, count=2)
    assert p.check(graph_with([0.95, 0.5]), 1, 1.0, {}) is None
    assert p.check(graph_with([0.95, 0.92, 0.1]), 1, 1.0, {}) is not None


def test_budget_exhausted_reads_stats():
    p = BudgetExhausted("node_visits", 10)
    assert p.check(EvidenceGraph(), 1, 1.0, {"node_visits": 9}) is None
    assert p.check(EvidenceGraph(), 1, 1.0, {"node_visits": 10}) is not None


def test_graph_diameter():
    p = GraphDiameter(max_nodes=2)
    assert p.check(graph_with([0.1]), 1, 1.0, {}) is None
    assert p.check(graph_with([0.1, 0.2, 0.3]), 1, 1.0, {}) is not None


def test_any_of_returns_first_firing_policy():
    p = AnyOf(ConfidenceThreshold(threshold=0.9, count=1), MaxIterations(limit=1))
    reason = p.check(graph_with([0.95]), 1, 1.0, {})
    assert reason is not None and reason.policy == "confidence_threshold"
    reason = p.check(graph_with([0.1]), 1, 1.0, {})
    assert reason is not None and reason.policy == "max_iterations"
