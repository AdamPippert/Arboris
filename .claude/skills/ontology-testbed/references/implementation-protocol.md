# Implementation protocol

The evaluator (`scripts/evaluate.py`) treats an Arboris implementation as a
black box with two methods. This file is the full contract for adapter
authors.

## The contract

```python
class MyImpl:
    def __init__(self):
        """Must be constructible with no arguments (the evaluator calls
        MyImpl()). Read hyperparameters from env vars or config files."""

    def fit(self, train_fixtures: list[dict]) -> None:
        """Called once, before any scoring, with the full training split.

        Each fixture: {"id", "name", "category", "source",
                       "graph": {"nodes": [...], "edges": [...]}}
        Nodes:  {"id", "name", "description", "attributes": [
                    {"name", "type", "is_identifier"} ]}
        Edges:  {"id", "source", "target", "relation", "cardinality",
                 "description"}

        Do anything here: gradient training, dendritic growth, statistics.
        There is no time limit, but keep dev-loop runs in minutes.
        """

    def score_edge(self, graph: dict, source: str, target: str) -> float:
        """Return a score; higher = more likely a relation source→target
        exists. Called many times per task with the SAME partial graph object
        (safe to cache per-graph computation keyed on id(graph)).

        `graph` is a dev/test fixture graph with the masked edges REMOVED.
        `source`/`target` are node ids in that graph.

        Scores only need to be comparable within one task. Ties against the
        true pair count as failure, so avoid constant outputs.
        """
```

## Evaluation rules

- Never load `tasks.json` or the dev/test fixtures yourself during `fit` —
  doing so is target leakage. The evaluator gives you exactly the training split.
- Determinism is strongly encouraged (seed everything); the harness itself is
  fully deterministic, so any run-to-run variance is yours.
- Report `--split test` numbers once per implementation version; iterate on
  `--split dev`.

## Wiring an implementation that lives in `src/arboris/`

```bash
PYTHONPATH=src python .claude/skills/ontology-testbed/scripts/evaluate.py \
    --impl arboris.eval.ontology_adapter:OntologyAdapter --split dev
```

The adapter should convert the fixture dicts into whatever graph-state
objects `arboris` uses internally, call the model's masked-relation scoring
path, and return the score. Keep the adapter thin: conversion + one forward
call. If the adapter grows model logic, that logic belongs in the library.

## Baselines to outperform

| Baseline | What it knows | Typical hits@1 (10 candidates) |
|---|---|---|
| `random` | nothing | ~0.10 |
| `degree` | partial-graph connectivity + train pair prior | well above random |

An implementation that cannot outperform `degree` has not learned relational
structure beyond connectivity. Whenever you report numbers, run both
baselines so results stay anchored to the same task set.
