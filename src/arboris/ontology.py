"""Versioned ontology contracts and executable graph validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .schemas import StateGraph, ValidationIssue


@dataclass(frozen=True)
class RelationRule:
    domains: frozenset[str]
    ranges: frozenset[str]


class Ontology:
    def __init__(self, document: dict):
        self.version = document["version"]
        self.types = frozenset(document["types"])
        self.required = {
            k: frozenset(v) for k, v in document.get("required_attributes", {}).items()
        }
        self.relations = {
            name: RelationRule(frozenset(rule["domains"]), frozenset(rule["ranges"]))
            for name, rule in document["relations"].items()
        }

    @classmethod
    def load(cls, path: Path) -> Ontology:
        return cls(json.loads(path.read_text()))

    def validate(self, graph: StateGraph) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        nodes = {node.id: node for node in graph.nodes}
        if len(nodes) != len(graph.nodes):
            issues.append(
                ValidationIssue(
                    code="duplicate_identity", severity="error", message="Duplicate node id"
                )
            )
        edge_ids = [edge.id for edge in graph.edges]
        if len(set(edge_ids)) != len(edge_ids):
            issues.append(
                ValidationIssue(
                    code="duplicate_identity", severity="error", message="Duplicate edge id"
                )
            )
        for node in graph.nodes:
            if node.type not in self.types:
                issues.append(
                    ValidationIssue(
                        code="unknown_type",
                        severity="error",
                        message=f"Unknown type {node.type}",
                        affected_ids=[node.id],
                    )
                )
            missing = self.required.get(node.type, frozenset()) - node.attributes.keys()
            if missing:
                issues.append(
                    ValidationIssue(
                        code="missing_property",
                        severity="error",
                        message=f"Missing required attributes: {sorted(missing)}",
                        affected_ids=[node.id],
                    )
                )
            states = node.attributes.get("states", [])
            if "Running" in states and "Stopped" in states:
                issues.append(
                    ValidationIssue(
                        code="exclusive_state",
                        severity="error",
                        message="Running and Stopped are mutually exclusive",
                        affected_ids=[node.id],
                    )
                )
        for edge in graph.edges:
            subject, obj = nodes.get(edge.subject_id), nodes.get(edge.object_id)
            if subject is None or obj is None:
                issues.append(
                    ValidationIssue(
                        code="dangling_reference",
                        severity="error",
                        message="Edge endpoint is missing",
                        affected_ids=[edge.id],
                        suggested_repair="Add endpoint or remove edge",
                    )
                )
                continue
            rule = self.relations.get(edge.predicate)
            if rule is None:
                issues.append(
                    ValidationIssue(
                        code="unknown_relation",
                        severity="error",
                        message=f"Unknown relation {edge.predicate}",
                        affected_ids=[edge.id],
                    )
                )
            elif subject.type not in rule.domains:
                issues.append(
                    ValidationIssue(
                        code="illegal_domain",
                        severity="error",
                        message=f"{edge.predicate} does not accept {subject.type} subjects",
                        affected_ids=[edge.id],
                    )
                )
            elif obj.type not in rule.ranges:
                issues.append(
                    ValidationIssue(
                        code="illegal_range",
                        severity="error",
                        message=f"{edge.predicate} does not accept {obj.type} objects",
                        affected_ids=[edge.id],
                    )
                )
        return issues

    def require_valid(self, graph: StateGraph) -> None:
        errors = [issue for issue in self.validate(graph) if issue.severity == "error"]
        if errors:
            raise ValueError("; ".join(f"{e.code}: {e.message}" for e in errors))
