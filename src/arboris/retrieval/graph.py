"""In-memory typed graph store.

Reference GraphStore implementation. Loads the testbed fixture format
(.claude/skills/ontology-testbed) directly, so the retrieval subsystem can be
exercised against the same 143-ontology corpus used to benchmark Arboris
implementations. Persistent / distributed stores implement the same protocol.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence


class InMemoryGraphStore:
    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: dict[str, dict[str, Any]] = {}
        self._incident: dict[str, list[str]] = defaultdict(list)

    # -- construction ------------------------------------------------------
    def add_node(self, node_id: str, **attrs: Any) -> None:
        self._nodes[node_id] = {"id": node_id, **attrs}

    def add_edge(self, edge_id: str, source: str, target: str, relation: str, **attrs: Any) -> None:
        if source not in self._nodes or target not in self._nodes:
            raise KeyError(f"edge {edge_id!r} references unknown node(s)")
        self._edges[edge_id] = {
            "id": edge_id,
            "source": source,
            "target": target,
            "relation": relation,
            **attrs,
        }
        self._incident[source].append(edge_id)
        self._incident[target].append(edge_id)

    @classmethod
    def from_fixture(cls, fixture: Mapping[str, Any]) -> "InMemoryGraphStore":
        """Build from an ontology-testbed fixture dict ({"graph": {"nodes",
        "edges"}}) or a bare {"nodes", "edges"} mapping."""
        graph = fixture.get("graph", fixture)
        store = cls()
        for n in graph["nodes"]:
            store.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
        for e in graph["edges"]:
            store.add_edge(
                e["id"],
                e["source"],
                e["target"],
                e.get("relation", ""),
                **{k: v for k, v in e.items() if k not in ("id", "source", "target", "relation")},
            )
        return store

    # -- GraphStore protocol ----------------------------------------------
    def node(self, node_id: str) -> Mapping[str, Any] | None:
        return self._nodes.get(node_id)

    def edge(self, edge_id: str) -> Mapping[str, Any] | None:
        return self._edges.get(edge_id)

    def node_ids(self) -> Iterable[str]:
        return self._nodes.keys()

    def neighbors(
        self, node_id: str, edge_types: Sequence[str] | None = None
    ) -> Iterable[Mapping[str, Any]]:
        for edge_id in self._incident.get(node_id, ()):
            edge = self._edges[edge_id]
            if edge_types is None or edge["relation"] in edge_types:
                yield edge

    # -- text views (what providers embed / score) -------------------------
    def node_text(self, node_id: str) -> str:
        n = self._nodes[node_id]
        return " ".join(str(n.get(k, "")) for k in ("name", "description") if n.get(k))

    def edge_text(self, edge_id: str) -> str:
        e = self._edges[edge_id]
        src = self._nodes[e["source"]].get("name", e["source"])
        tgt = self._nodes[e["target"]].get("name", e["target"])
        return f'{src} {e["relation"]} {tgt} {e.get("description", "")}'.strip()
