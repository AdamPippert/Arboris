# RFC-0001: The retrieval pipeline and its interfaces

**Status:** Implemented (reference implementation) · relates to ADR-0001

## Summary

Retrieval iteratively constructs the smallest coherent evidence graph.
This Request for Comments (RFC) specifies the pipeline stages, the data
model, the interface layer, and the multi-scale, edge-aware scoring
design. Code: `src/arboris/retrieval/`.

## Data model (`types.py`)

| Type | Role |
|---|---|
| `Query` | immutable evidence request: text, target `Scale`s, `RetrievalHint`s |
| `Candidate` | stage-1 recall output: cheap, high-recall, unranked for precision |
| `Evidence` | scored graph item (`kind`: node/edge/path) with per-channel scores preserved |
| `EvidenceGraph` | the product: nodes + edges + evidence scores; `total_mass` drives info-gain |
| `Hypothesis` | one speculative retrieval line with a prior |
| `RetrievalTrace` / `TraceEvent` | complete, serializable observability record |
| `RetrievalResult` | evidence + trace + per-hypothesis graphs |

`Scale` spans document-shaped corpora (repository → document → paragraph →
sentence). It also spans code-shaped corpora (repository → file → object →
function → basic block → statement) and graph granularities (node, edge,
path). One enum lets the engine fuse across scales without special-casing
corpus type.

## Pipeline stages (`engine.py`)

```
Query
  └─ HypothesisManager.propose() ──► N hypotheses, run concurrently
       loop (per hypothesis, until ConvergencePolicy fires):
         1. dense recall      all DenseRetrievers × all frontier queries,
                              asyncio.gather — maximize recall
         2. late interaction  LateInteractionRetriever.rerank on the
                              candidate set only — maximize precision
         3. activation        ActivationEngine.spread from current evidence;
            + expansion       ExpansionPolicy picks the frontier; subgraph
                              is closed over edges between evidence nodes
         4. frontier fan-out  each frontier node becomes an independent
                              retrieval problem (the next loop's queries)
  └─ EvidenceMerger.merge() ──► single EvidenceGraph (the only sync point)
```

Design rules:
- Stage 1 never ranks for precision; stage 2 never sees non-candidates.
- Expansion follows typed edges only through policy. Parents, children,
  ontology links, and temporal/causal/semantic neighbors are relation
  types on the graph. `ExpansionPolicy` filters them; no traversal is
  hardcoded.
- Synchronization happens at merge points only (`asyncio.gather` at recall
  fan-out; `EvidenceMerger` across hypotheses). Everything between is
  independent. That independence makes distributed and accelerated
  execution a deployment change, not a redesign.

## Interfaces (`interfaces.py`)

`GraphStore`, `EmbeddingProvider`, `LateInteractionProvider`, `Retriever`,
`DenseRetriever`, `LateInteractionRetriever`, `GraphRetriever`,
`NodeScorer`, `EdgeScorer`, `PathScorer`, `ActivationEngine`,
`ExpansionPolicy`, `GraphExpander`, `ConvergencePolicy`,
`HypothesisManager`, `EvidenceMerger`.

All are structural `Protocol`s: implementations register in `registry.py`,
and callers select them by name. Interfaces are async where I/O or model
batching happens (retrievers, expanders). They are sync where computation
is local (providers, activation, policies). The engine composes protocols
and holds no model or reasoning logic.

### Model agnosticism

The registry is the only place model families appear, as names. Expected
early adapters: `"denseon"`, `"mdenseon"` (dense recall), `"lateon"`,
`"mlateon"` (late interaction). Each is an optional extra outside the
core package, implementing
`EmbeddingProvider`/`LateInteractionProvider`. The reference
`hash`/`hash-late` providers (`providers.py`) implement the same protocols
deterministically with zero dependencies. They are test doubles, not
retrievers, and the documentation says so.

## Multi-scale and edge-aware scoring

- A `LateInteractionProvider` declares the `Scale`s it serves; multiple
  providers can coexist, one per granularity or one spanning several.
- Edges are scoreable evidence: they carry text, type, weight, direction,
  and timestamp metadata. `GraphStore.edge_text()` gives providers a
  scoring view. The reference reranker scores node↔query and edge↔query as
  separate channels and records both in `Evidence.channels`. `PathScorer`
  extends the same pattern to paths.
- Fusion: `Evidence.channels` keeps every scorer's contribution; mergers
  and downstream consumers can re-weight without re-running retrieval.

## Backwards compatibility

None required (greenfield — see ADR-0001 audit). The public package gains
`arboris.retrieval`; nothing existing changes. The testbed fixture format
is the interchange: `InMemoryGraphStore.from_fixture()` accepts it
unchanged.

## Testing

`tests/test_retrieval_engine.py` runs the full pipeline on testbed
fixtures (network-free fallback included): evidence-graph shape, trace
completeness, convergence reporting, hypothesis merge, hint behavior,
determinism. Separate unit tests cover policies and activation.

## Roadmap

1. Real model adapters behind the registry (optional extras).
2. Persistent `GraphStore` (same protocol) and index lifecycle.
3. `GraphRetriever` adapters (typed lookups, path queries).
4. Distributed execution: hypothesis- and frontier-level sharding.
5. Accelerator offload of late-interaction scoring (the interaction kernel
   is the FPGA/GPU-friendly hot spot; protocols already isolate it).
