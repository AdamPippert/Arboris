import asyncio

from arboris.retrieval import (
    ActivationFrontier,
    AnyOf,
    GraphDenseRetriever,
    GraphLateInteractionRetriever,
    Hypothesis,
    InMemoryGraphStore,
    MaxIterations,
    MinInformationGain,
    Query,
    RetrievalEngine,
    RetrievalHint,
    SpreadingActivation,
)


def make_engine(store, convergence=None, hypotheses=None):
    return RetrievalEngine(
        graph=store,
        dense=[GraphDenseRetriever(store)],
        late=GraphLateInteractionRetriever(store),
        activation=SpreadingActivation(default_weight=0.8),
        expansion=ActivationFrontier(min_activation=0.01, max_frontier=4),
        convergence=convergence or AnyOf(MinInformationGain(0.05), MaxIterations(3)),
        hypotheses=hypotheses,
    )


def run(coro):
    return asyncio.run(coro)


def test_end_to_end_produces_evidence_graph(coffee_fixture):
    store = InMemoryGraphStore.from_fixture(coffee_fixture)
    engine = make_engine(store)
    result = run(engine.retrieve(Query(text="customer places an order for coffee")))
    assert result.evidence.nodes, "expected a non-empty evidence graph"
    assert result.evidence.scores
    # evidence contains graph structure, not just hits: edges between accepted nodes
    if len(result.evidence.nodes) > 1:
        assert result.evidence.edges
    # the top item should be semantically related to the query
    top = max(result.evidence.scores.values(), key=lambda e: e.score)
    assert top.item_id in {"customer", "order"}


def test_trace_records_every_stage(coffee_fixture):
    store = InMemoryGraphStore.from_fixture(coffee_fixture)
    result = run(make_engine(store).retrieve(Query(text="coffee order")))
    stages = set(result.trace.stages())
    for required in ("hypotheses", "dense_recall", "late_interaction", "activation_expansion", "convergence", "merge"):
        assert required in stages, f"missing {required} in trace"
    assert result.trace.convergence is not None


def test_convergence_reason_is_reported(coffee_fixture):
    store = InMemoryGraphStore.from_fixture(coffee_fixture)
    engine = make_engine(store, convergence=AnyOf(MaxIterations(1)))
    result = run(engine.retrieve(Query(text="supplier")))
    assert result.trace.convergence.policy == "max_iterations"


def test_multiple_hypotheses_run_and_merge(coffee_fixture):
    store = InMemoryGraphStore.from_fixture(coffee_fixture)

    class TwoHypotheses:
        def propose(self, query):
            return [
                Hypothesis(hypothesis_id="a", query=Query(text="customer order"), prior=1.0),
                Hypothesis(hypothesis_id="b", query=Query(text="supplier bean"), prior=0.5),
            ]

    engine = make_engine(store, hypotheses=TwoHypotheses())
    result = run(engine.retrieve(Query(text="where do the beans in my order come from")))
    assert set(result.hypotheses) == {"a", "b"}
    # merged graph unions both lines of evidence
    assert set(result.evidence.nodes) >= set(result.hypotheses["a"].nodes)
    assert set(result.evidence.nodes) >= set(result.hypotheses["b"].nodes)
    # hypothesis channel survives the merge for auditability
    assert any("hypothesis" in ev.channels for ev in result.evidence.scores.values())


def test_hints_bias_but_do_not_bypass_scoring(coffee_fixture):
    store = InMemoryGraphStore.from_fixture(coffee_fixture)
    engine = make_engine(store)
    hinted = Query(
        text="customer",
        hints=(RetrievalHint(kind="missing_evidence", payload={"text": "supplier bean"}, source="sgjm"),),
    )
    result = run(engine.retrieve(hinted))
    # the hint opened a second line of recall; scored evidence may include it,
    # but every scored item carries scoring channels (nothing enters unscored)
    assert all(ev.channels for ev in result.evidence.scores.values())


def test_determinism(coffee_fixture):
    store = InMemoryGraphStore.from_fixture(coffee_fixture)
    q = Query(text="coffee store order")
    r1 = run(make_engine(store).retrieve(q))
    r2 = run(make_engine(store).retrieve(q))
    assert {k: v.score for k, v in r1.evidence.scores.items()} == {
        k: v.score for k, v in r2.evidence.scores.items()
    }
