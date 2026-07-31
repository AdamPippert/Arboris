# ADR-0001: Retrieval is a first-class, graph-native subsystem

**Status:** Accepted · 2026-07
**Deciders:** Adam Pippert (project lead)

## Context

Arboris is a graph-native cognitive architecture, not a transformer
replacement. Its major components are: transformer(s) for perception and
expression; a retrieval system for perception/search; a typed semantic graph
as persistent knowledge; a dendritic fabric for activation and routing; the
SGJM (the predictive world model over the typed semantic graph, described in
`docs/architecture.md` and `docs/training-pipeline.md`); an executive layer
for planning; and memory packs for modular long-term knowledge.

**Repository audit (2026-07):** there is no existing retrieval architecture.
The repo contains the pre-alpha scaffold, design docs, and the ontology
testbed. This ADR is therefore a greenfield decision, not a migration: there
is no legacy dense-vector top-K path to preserve, and no backwards
compatibility constraint beyond "don't break the public `arboris` package".

The conventional design — embed everything, cosine top-K, hand documents to
the model — treats retrieval as a lookup table. That is the wrong shape for
Arboris: knowledge lives in a typed graph, relevance propagates along
relations, and what reasoning needs is not "K similar documents" but the
smallest coherent evidence subgraph.

## Decision

1. **Retrieval is Arboris's sensory cortex.** It perceives and assembles
   *evidence*; it never reasons. The engine's output is an `EvidenceGraph`
   plus a complete `RetrievalTrace` — never a raw hit list, never an answer.
   The reasoning/expression components consume evidence downstream. These
   concerns are separated at the interface level and must not be mixed.

2. **The pipeline is iterative and graph-native**, replacing
   `query → top-K` with:
   `query → parallel dense recall → late-interaction precision → dendritic
   activation → graph expansion → parallel frontier retrieval → convergence →
   merge`. Stopping is a policy ("smallest coherent evidence graph"), of
   which top-K is one degenerate case. Implemented in
   `src/arboris/retrieval/engine.py`; detailed design in RFC-0001.

3. **The subsystem is model-agnostic by construction.** All behavior sits
   behind protocols (`interfaces.py`); concrete models are adapters selected
   by name through a registry (`registry.py`). Late-interaction and dense
   model families we expect to adapt first — e.g. registry names
   "denseon"/"mdenseon" (dense recall) and "lateon"/"mlateon" (late
   interaction) — are configuration values. No vendor is imported by the
   engine, ever.

4. **Relationships are first-class evidence.** Edges (and paths) are
   embeddable and scorable independently of nodes (`NodeScorer`,
   `EdgeScorer`, `PathScorer`); evidence records preserve per-channel scores.

5. **The dendritic fabric drives search locality.** Graph traversal is not
   uniform: activation energy spreads from evidence along typed edges with
   configurable conductances and distance decay (RFC-0002). This is the same
   architectural motif as the dendritic training mechanism — capacity and
   attention go where signal lives.

6. **Speculation is native.** Multiple hypotheses retrieve independently and
   merge only after scoring; SGJM predictions enter as `RetrievalHint`s that
   bias recall but never bypass scoring (RFC-0002).

## Alternatives considered

- **Off-the-shelf vector store + top-K** — rejected: flattens the graph,
  fixes K a priori, no relation awareness, couples us to one model family.
- **Retrieval inside the world model (SGJM performs retrieval)** — rejected:
  mixes prediction with perception; SGJM instead *hints* retrieval.
- **Graph database query language (SPARQL/Cypher) as retrieval** — rejected
  as the primary path: exact-match semantics, no learned relevance; remains
  compatible as a `GraphRetriever` adapter.

## Consequences

- Positive: model swaps are configuration; every run is observable and
  replayable; the evidence-graph contract gives reasoning a stable input
  shape; async fan-out with a single merge point maps naturally to
  distributed and accelerator execution.
- Negative / accepted costs: more moving parts than top-K; reference
  providers are deliberately non-competitive (hash-based) so early quality
  numbers say nothing about model quality; convergence policies need tuning
  per corpus.
- The ontology testbed corpus doubles as retrieval test data
  (`InMemoryGraphStore.from_fixture`), keeping the sensory cortex and the
  world-model benchmarks on the same ground truth.

## Implementation status

Interfaces, reference implementations, and tests landed with this ADR
(`src/arboris/retrieval/`, `tests/test_retrieval_*.py`). Real model
adapters, persistent graph stores, and distributed execution are future
increments (see RFC-0001 §Roadmap).
