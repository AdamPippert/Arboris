# ADR-0001: Retrieval is a first-class, graph-native subsystem

**Status:** Accepted · 2026-07
**Deciders:** Adam Pippert (project lead)

This Architecture Decision Record (ADR) makes retrieval a first-class,
graph-native subsystem of Arboris. The decision comes first; context,
alternatives, and consequences follow.

## Decision

1. **Retrieval is Arboris's sensory cortex**. It perceives and assembles
   *evidence*; it never reasons. The engine outputs an `EvidenceGraph` plus
   a complete `RetrievalTrace`. It never outputs a raw hit list or an
   answer. The reasoning and expression components consume evidence
   downstream. The interface separates these concerns; implementations must
   not mix them.

2. **The pipeline is iterative and graph-native**. It replaces
   `query → top-K` with:
   `query → parallel dense recall → late-interaction precision → dendritic
   activation → graph expansion → parallel frontier retrieval → convergence →
   merge`. Stopping is a policy ("smallest coherent evidence graph"). Top-K
   is one degenerate case of that policy. `src/arboris/retrieval/engine.py`
   implements the pipeline; RFC-0001 gives the detailed design.

3. **The subsystem is model-agnostic by construction**. All behavior sits
   behind protocols (`interfaces.py`). Concrete models are adapters,
   selected by name through a registry (`registry.py`). The late-interaction
   and dense model families we expect to adapt first are configuration
   values. Examples are the registry names "denseon"/"mdenseon" (dense
   recall) and "lateon"/"mlateon" (late interaction). The engine never
   imports a vendor.

4. **Relationships are first-class evidence**. Edges and paths are
   embeddable and scorable independently of nodes (`NodeScorer`,
   `EdgeScorer`, `PathScorer`). Evidence records preserve per-channel
   scores.

5. **The dendritic fabric drives search locality**. Graph traversal is not
   uniform. Activation energy spreads from evidence along typed edges, with
   configurable conductances and distance decay (RFC-0002). The dendritic
   training mechanism uses the same architectural motif: capacity and
   attention concentrate where the signal is.

6. **Speculation is native**. Multiple hypotheses retrieve independently
   and merge only after scoring. Predictions from the SGJM (the predictive
   world model) enter as `RetrievalHint`s. Hints bias recall but never
   bypass scoring (RFC-0002).

## Context

Arboris is a graph-native cognitive architecture, not a transformer
replacement. Its major components are transformer(s) for perception and
expression, a retrieval system for perception and search, and a typed
semantic graph as persistent knowledge. A dendritic fabric handles
activation and routing. The SGJM is the predictive world model over the
typed semantic graph, described in `docs/architecture.md` and
`docs/training-pipeline.md`. An executive layer handles planning, and
memory packs hold modular long-term knowledge.

**Repository audit (2026-07):** there is no existing retrieval
architecture. The repository contains the pre-alpha scaffold, design docs, and
the ontology testbed. This ADR is therefore a greenfield decision, not a
migration. No legacy dense-vector top-K path exists to preserve. The only
backwards compatibility constraint is "don't break the public `arboris`
package".

The conventional design — embed everything, cosine top-K, hand documents
to the model — treats retrieval as a lookup table. That shape is wrong for
Arboris. Knowledge lives in a typed graph, and relevance propagates along
relations. Reasoning needs the smallest coherent evidence subgraph, not "K
similar documents".

## Alternatives considered

- **Off-the-shelf vector store + top-K** — rejected: flattens the graph,
  fixes K a priori, no relation awareness, couples us to one model family.
- **Retrieval inside the world model (SGJM performs retrieval)** — rejected:
  mixes prediction with perception; SGJM instead *hints* retrieval.
- **Graph database query language (SPARQL/Cypher) as retrieval** — rejected
  as the primary path: exact-match semantics, no learned relevance; remains
  compatible as a `GraphRetriever` adapter.

## Consequences

- Positive: model swaps are configuration, and every run is observable and
  replayable. The evidence-graph contract gives reasoning a stable input
  shape. Async fan-out with a single merge point maps naturally to
  distributed and accelerator execution.
- Negative (accepted costs): the design has more components than top-K.
  Reference providers are deliberately non-competitive (hash-based), so
  early quality numbers say nothing about model quality. Convergence
  policies need tuning per corpus.
- The ontology testbed corpus also serves as retrieval test data
  (`InMemoryGraphStore.from_fixture`). One corpus keeps the sensory cortex
  and the world-model benchmarks on the same ground truth.

## Implementation status

Interfaces, reference implementations, and tests accompany this ADR
(`src/arboris/retrieval/`, `tests/test_retrieval_*.py`). Real model
adapters, persistent graph stores, and distributed execution are future
increments (see RFC-0001 §Roadmap).
