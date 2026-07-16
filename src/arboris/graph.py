"""Deterministic and reversible graph transformations."""

from copy import deepcopy

from .schemas import GraphDelta, StateGraph


def diff_graphs(before: StateGraph, after: StateGraph) -> GraphDelta:
    before_nodes = {n.id: n for n in before.nodes}
    after_nodes = {n.id: n for n in after.nodes}
    before_edges = {e.id: e for e in before.edges}
    after_edges = {e.id: e for e in after.edges}
    return GraphDelta(
        added_nodes=[after_nodes[k] for k in sorted(after_nodes.keys() - before_nodes.keys())],
        removed_node_ids=sorted(before_nodes.keys() - after_nodes.keys()),
        changed_nodes=[
            after_nodes[k]
            for k in sorted(before_nodes.keys() & after_nodes.keys())
            if before_nodes[k] != after_nodes[k]
        ],
        added_edges=[after_edges[k] for k in sorted(after_edges.keys() - before_edges.keys())],
        removed_edge_ids=sorted(before_edges.keys() - after_edges.keys()),
    )


def apply_delta(graph: StateGraph, delta: GraphDelta, *, graph_id: str | None = None) -> StateGraph:
    """Apply a delta without mutating the input snapshot."""
    nodes = {node.id: deepcopy(node) for node in graph.nodes}
    edges = {edge.id: deepcopy(edge) for edge in graph.edges}
    for node_id in delta.removed_node_ids:
        nodes.pop(node_id, None)
    for node in [*delta.changed_nodes, *delta.added_nodes]:
        nodes[node.id] = deepcopy(node)
    for edge_id in delta.removed_edge_ids:
        edges.pop(edge_id, None)
    for edge in delta.added_edges:
        edges[edge.id] = deepcopy(edge)
    return graph.model_copy(
        update={
            "graph_id": graph_id or graph.graph_id,
            "nodes": [nodes[key] for key in sorted(nodes)],
            "edges": [edges[key] for key in sorted(edges)],
        }
    )


def invert_delta(before: StateGraph, delta: GraphDelta) -> GraphDelta:
    """Create an inverse using the source snapshot as the rollback journal."""
    before_nodes = {node.id: node for node in before.nodes}
    before_edges = {edge.id: edge for edge in before.edges}
    return GraphDelta(
        added_nodes=[before_nodes[key] for key in delta.removed_node_ids],
        removed_node_ids=[node.id for node in delta.added_nodes],
        changed_nodes=[before_nodes[node.id] for node in delta.changed_nodes],
        added_edges=[before_edges[key] for key in delta.removed_edge_ids],
        removed_edge_ids=[edge.id for edge in delta.added_edges],
    )
