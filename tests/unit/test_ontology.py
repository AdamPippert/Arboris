from pathlib import Path

from arboris.ontology import Ontology
from arboris.schemas import GraphEdge, GraphNode, StateGraph

ONTOLOGY = Path(__file__).parents[2] / "ontologies/domains/infrastructure-0.1.0.json"


def valid_graph() -> StateGraph:
    return StateGraph(
        graph_id="g",
        ontology_version="infrastructure-0.1.0",
        nodes=[
            GraphNode(id="c", type="Cluster", attributes={"name": "cluster"}),
            GraphNode(id="n", type="Node", attributes={"name": "node", "schedulable": True}),
            GraphNode(id="p", type="Pod", attributes={"name": "pod", "phase": "Running"}),
        ],
        edges=[GraphEdge(id="e", subject_id="p", predicate="scheduled_on", object_id="n")],
    )


def test_valid_graph_has_no_issues() -> None:
    assert Ontology.load(ONTOLOGY).validate(valid_graph()) == []


def test_illegal_domain_and_dangling_reference_are_actionable() -> None:
    graph = valid_graph()
    graph.edges.extend(
        [
            GraphEdge(id="bad-domain", subject_id="n", predicate="scheduled_on", object_id="n"),
            GraphEdge(id="dangling", subject_id="missing", predicate="part_of", object_id="c"),
        ]
    )
    issues = Ontology.load(ONTOLOGY).validate(graph)
    assert {issue.code for issue in issues} == {"illegal_domain", "dangling_reference"}
    assert next(issue for issue in issues if issue.code == "dangling_reference").suggested_repair


def test_missing_required_property_is_rejected() -> None:
    graph = valid_graph()
    graph.nodes[0].attributes.clear()
    assert "missing_property" in {issue.code for issue in Ontology.load(ONTOLOGY).validate(graph)}
