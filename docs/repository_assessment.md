# Repository assessment

Assessment date: 2026-07-16. Baseline commit: `e7dafdf` (`main`). This document
describes the repository as found before the current uncommitted migration work.

## Executive summary

The repository was a packaging and documentation seed, not an executable research
platform. It contained an Apache-2.0 license, notice, a short README, a setuptools
`pyproject.toml`, and `src/arboris/__init__.py` exposing version `0.0.1`. There were
no model, graph, data, training, evaluation, configuration, CLI, CI, notebook, or
test implementations. The only untracked pre-existing file was `error.log`; it is
not part of this assessment and remains untouched.

The initial test command failed before collection because `pytest` was not installed
in the host interpreter. No test files existed. Python 3.14.5, PyTorch, NumPy, and
PyYAML were locally visible; Pydantic, PyArrow, Kuzu, Typer, pytest, and PyG were not.

## Current repository state

| Area | Status | Evidence and disposition |
|---|---|---|
| Package identity | PARTIAL | `arboris` name/version exists and is reusable. |
| Packaging | PARTIAL | Valid setuptools seed, but no runtime/dev dependencies or CLI. |
| Documentation | PARTIAL | README states the research direction honestly; retain and expand. |
| Licensing | READY | Apache-2.0 `LICENSE` and `NOTICE`; preserve. |
| Public API | PARTIAL | Only `__version__`; preserve during migration. |
| Graph model | MISSING | No graph types, workspace, mutations, or serialization. |
| Ontology | MISSING | No ontology or executable constraints. |
| Perception | DEFERRED | No implementation; not needed for infrastructure-first slice. |
| Dendritic compute | MISSING | No branches, routing, soma, or diagnostics. |
| Prediction/SGJM | MISSING | No encoder, EMA target, predictor, or objectives. |
| Hypotheses/arbitration | MISSING | No candidate or scoring mechanism. |
| Memory | MISSING | No working, episodic, semantic, or procedural interfaces. |
| Data/simulation | MISSING | No loader, dataset, simulator, or provenance pipeline. |
| Training/evaluation | MISSING | No loop, metrics, checkpointing, or experiment ledger. |
| Tests | BLOCKED | No tests; host environment initially lacked pytest. |
| CI/automation | MISSING | No workflows, lint, type check, or pre-commit configuration. |

## Functional and reusable components

- The project name, module namespace, version seed, Apache licensing, author and
  project metadata are reusable.
- The README's statement that the work is pre-alpha and has no released weights is
  accurate and should remain until experiment evidence changes it.
- The `src/` package layout is conventional and avoids a disruptive packaging move.

There are no prototypes to refactor and no implemented behavior to deprecate. The
README layout description will need expansion, not removal.

## Existing flows

There is no data, training, or inference flow. Importing `arboris` is the only public
behavior. No external database or service is configured.

## Gap analysis against the target architecture

| Target component | Classification | First evidence required |
|---|---|---|
| Perception layer | DEFERRED | Backend-neutral protocol and mock encoder after graph slice. |
| Semantic workspace | MISSING | Typed snapshot, deterministic reversible mutations, provenance. |
| Dendritic compute fabric | MISSING | Multi-branch dendritron with sparse gates and soma diagnostics. |
| Prediction engine | MISSING | Tiny latent transition task with stable target interface. |
| Arbitration/executive | MISSING | Two candidates, explicit score terms, select/abstain behavior. |
| Memory system | DEFERRED | Repository interfaces before persistent implementations. |
| Output/action | DEFERRED | Typed prediction output; language generation is out of scope. |
| Evaluation framework | MISSING | Baseline, metrics, experiment manifest, reload test. |
| Infrastructure ontology | MISSING | Versioned types, relation contracts, executable constraints. |
| Reproducible environment | PARTIAL | Dependency declaration, lock file and clean install proof needed. |

## Risks and blockers

- Kuzu, PyArrow, and Pydantic require installing declared dependencies. This is an
  environment operation, not an architectural blocker.
- The two supplied briefs emphasize different first worlds: infrastructure state
  transitions versus a generic synthetic world. The migration uses the bounded
  infrastructure simulator as the synthetic world so both goals share one dataset.
- The later brief asks for transformer perception in the architectural path, while
  the earlier brief explicitly postpones language. The initial perception boundary
  will accept structured observations; transformer integration remains deferred.
- Structural plasticity and persistent memory are interfaces only until prediction
  and arbitration have measurable baselines.

## Audit limitations

Test coverage could not be measured because no tests existed. No notebooks, CI,
training scripts, data loaders, graph code, or experiment artifacts were available
to inspect. This is a complete audit of tracked files at the baseline commit.
