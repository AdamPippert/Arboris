from arboris.graph import apply_delta, diff_graphs, invert_delta
from arboris.schemas import GraphEdge, GraphNode, StateGraph


def graph(graph_id: str, phase: str, include_edge: bool) -> StateGraph:
    nodes = [
        GraphNode(id="cluster", type="Cluster", attributes={"name": "c"}),
        GraphNode(id="pod", type="Pod", attributes={"name": "p", "phase": phase}),
    ]
    edges = (
        [GraphEdge(id="member", subject_id="pod", predicate="part_of", object_id="cluster")]
        if include_edge
        else []
    )
    return StateGraph(
        graph_id=graph_id, nodes=nodes, edges=edges, ontology_version="infrastructure-0.1.0"
    )


def test_diff_apply_and_rollback() -> None:
    before = graph("before", "Running", True)
    after = graph("after", "Terminated", False)
    delta = diff_graphs(before, after)
    rebuilt = apply_delta(before, delta, graph_id="after")
    assert rebuilt == after
    rolled_back = apply_delta(rebuilt, invert_delta(before, delta), graph_id="before")
    assert rolled_back == before


def test_apply_does_not_mutate_source() -> None:
    before = graph("before", "Running", True)
    frozen = before.model_copy(deep=True)
    apply_delta(before, diff_graphs(before, graph("after", "Failed", False)))
    assert before == frozen
