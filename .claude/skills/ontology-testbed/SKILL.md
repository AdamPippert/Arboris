---
name: ontology-testbed
description: >
  Evaluate and train Arboris implementations against real typed
  entity-relation ontologies. Microsoft's Ontology-Playground catalogue (71
  ontologies — retail, healthcare, finance/FIBO, manufacturing, …) is the
  masked-relation-prediction benchmark; the schema.org vocabulary (~720
  types) is an optional training-enrichment corpus. Use this skill whenever
  the user wants to test an Arboris implementation, run the ontology
  benchmark, or build graph test fixtures. Also use it to add or convert an
  ontology corpus (schema.org, playground, or a new source), or to compare a
  model against the baselines. Trigger on "the testbed", "ontology
  fixtures", or "masked relation prediction". Also trigger when the user
  wants to evaluate or train a graph or world-model implementation against
  real ontologies, even without naming the corpora.
---

# Ontology testbed for Arboris implementations

This skill turns the public catalogue of
[Microsoft Ontology-Playground](https://github.com/microsoft/Ontology-Playground)
(live app: <https://microsoft.github.io/Ontology-Playground/>) into a
train/dev/test benchmark for Arboris implementations. Each catalogue entry is a
typed entity-relation ontology — exactly the graph-state shape Arboris models
(see `docs/architecture.md`). The benchmark task is **masked-relation
prediction**: hide some relations, then ask the implementation to rank the
true endpoints against distractors. The task matches the masked-relation
objective in `docs/training-pipeline.md`. The testbed therefore exercises the
same capability the real training pipeline will optimize.

All scripts are stdlib-only Python (≥3.10) and deterministic: same catalogue
snapshot in → byte-identical fixtures, splits, and tasks out.

## Workflow

Run the three steps from the repository root. The scripts write fixtures to
`tests/fixtures/ontology-playground/` (gitignored — generated data, not
source).

```bash
# 1. Fetch the catalogue (cached; pass --refresh to re-download)
python .claude/skills/ontology-testbed/scripts/fetch_catalogue.py

# 1b. (optional, recommended) add schema.org as a second corpus — ~720 types,
#     ~1160 typed relations, converted into subtree fixtures plus one
#     full-vocabulary training fixture (see references/schemaorg-format.md)
python .claude/skills/ontology-testbed/scripts/schemaorg_fixtures.py

# 2. Build graph fixtures, train/dev/test splits, and masked-relation tasks
#    (automatically merges any extra-fixtures-*.json in the fixtures dir)
python .claude/skills/ontology-testbed/scripts/build_fixtures.py

# 3. Evaluate an implementation (builtin baselines: random, degree)
python .claude/skills/ontology-testbed/scripts/evaluate.py --impl degree
python .claude/skills/ontology-testbed/scripts/evaluate.py --impl random
```

`evaluate.py` prints per-category and aggregate **hits@1** and **MRR** (mean
reciprocal rank), and writes a JSON report next to the fixtures. Always run the `degree` baseline
alongside a candidate implementation — a real model must outperform it, and
the random baseline gives the floor (~1/#candidates).

## Evaluating a real Arboris implementation

An implementation is any Python class with two methods (full contract:
`references/implementation-protocol.md` — read it before writing an adapter):

```python
class MyImpl:
    def fit(self, train_fixtures: list[dict]) -> None:
        """Train on the training-split fixtures (full graphs)."""
    def score_edge(self, graph: dict, source: str, target: str) -> float:
        """Higher = more likely a relation source→target exists.
        `graph` is a partial fixture graph with masked edges removed."""
```

Point the evaluator at it with a `module:Class` spec (the module must be
importable, e.g. from the repo root with `src/` on `PYTHONPATH`):

```bash
PYTHONPATH=src python .claude/skills/ontology-testbed/scripts/evaluate.py \
    --impl mypackage.mymodel:MyImpl
```

Training against the testbed means whatever `fit` does with the train split
(gradient training, structure growth, statistics). The evaluator never shows
implementations the dev/test masked edges; `--split dev` is for iteration,
`--split test` for final numbers. Report test-split numbers only once per
implementation version — repeated test-split peeking is overfitting.

## Corpora

| Corpus | Fixtures | Role | Notes |
|---|---|---|---|
| Ontology-Playground catalogue | 71 small ontologies | train + **eval core** | hand-authored, diverse domains |
| schema.org (optional) | ~71 subtree fixtures + 1 full-vocabulary fixture | mostly **training enrichment** | web-scale vocabulary; `subTypeOf` edges are context only (never masked); the full fixture is pinned to train with dev/test pairs held out to prevent leakage |

New corpora follow the same pattern: write a converter that emits
`extra-fixtures-<name>.json` into the fixtures dir and re-run
`build_fixtures.py`. Edges may set `"maskable": false` to serve as context
without becoming eval targets, and a fixture may pin `"split": "train"`.

## Fixture and task format

- Fixture: `{"id", "name", "category", "source", "graph": {"nodes": [...], "edges": [...]}}`
  — nodes are entity types (id, name, attribute schema), edges are typed
  relations (source, target, relation name, cardinality).
- Task: one masked edge + `n_distractors` false `(source, target)` pairs,
  shuffled; the implementation's scores rank them.

Details, provenance, and licensing notes: `references/catalogue-format.md`.

## Interpreting results

- **hits@1**: fraction of tasks where the true pair ranked first (ties count
  as failures — deterministic and strict).
- **MRR**: mean reciprocal rank of the true pair.
- Category breakdown matters: the `fibo` (finance) and `school` ontologies
  differ structurally from `retail`/`manufacturing`. An implementation that
  wins on only one category is memorizing surface statistics, not learning
  relational structure.

## Troubleshooting

- **Fetch fails / offline**: `fetch_catalogue.py --cache-only` reuses the last
  snapshot; commit environments can also set `ONTOLOGY_CATALOGUE_PATH` to a
  local `catalogue.json`.
- **Different numbers than a teammate**: compare the `catalogue_sha256` in the
  fixtures manifest — the upstream catalogue evolves; pin a snapshot for
  comparable results.
- **New Arboris code doesn't import**: the harness deliberately has no
  dependency on `arboris` internals; only the adapter class needs to import.
