from arboris.retrieval import (
    InMemoryGraphStore,
    SpreadingActivation,
    exponential_decay,
    harmonic_decay,
    linear_decay,
)


def chain_store(n=5):
    s = InMemoryGraphStore()
    for i in range(n):
        s.add_node(f"n{i}", name=f"node {i}")
    for i in range(n - 1):
        s.add_edge(f"e{i}", f"n{i}", f"n{i+1}", "causes")
    return s


def test_activation_decays_with_distance():
    s = chain_store()
    field = SpreadingActivation(decay=exponential_decay(0.5), default_weight=1.0, max_hops=4).spread(
        s, {"n0": 1.0}
    )
    assert field["n0"] == 1.0
    assert field["n1"] > field["n2"] > field["n3"] > field["n4"]


def test_edge_type_modulates_propagation():
    s = InMemoryGraphStore()
    for nid in ("seed", "causal", "weak"):
        s.add_node(nid, name=nid)
    s.add_edge("a", "seed", "causal", "causes")
    s.add_edge("b", "seed", "weak", "references")
    engine = SpreadingActivation(
        edge_weights={"causes": 1.0, "references": 0.1}, default_weight=0.5, max_hops=1
    )
    field = engine.spread(s, {"seed": 1.0})
    assert field["causal"] > field["weak"]


def test_decay_functions_shapes():
    assert exponential_decay(0.5)(2) == 0.25
    assert harmonic_decay()(3) == 0.25
    assert linear_decay(radius=4)(2) == 0.5
    assert linear_decay(radius=4)(6) == 0.0


def test_spread_is_deterministic():
    s = chain_store(6)
    e = SpreadingActivation()
    assert e.spread(s, {"n0": 1.0, "n5": 0.5}) == e.spread(s, {"n0": 1.0, "n5": 0.5})


def test_threshold_prunes_far_energy():
    s = chain_store(10)
    field = SpreadingActivation(
        decay=exponential_decay(0.3), default_weight=1.0, max_hops=9, threshold=0.05
    ).spread(s, {"n0": 1.0})
    assert "n9" not in field
