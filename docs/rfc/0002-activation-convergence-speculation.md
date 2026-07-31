# RFC-0002: Dendritic activation, convergence, speculation, and SGJM hints

**Status:** Implemented (reference implementation) · relates to ADR-0001

This Request for Comments (RFC) specifies four retrieval mechanisms:
dendritic activation, convergence policies, speculative retrieval, and
hints from the SGJM (the predictive world model).

## Dendritic activation (`activation.py`)

The dendritic fabric decides *where retrieval looks next*. Instead of
uniform traversal, evidence nodes inject activation energy that spreads
along edges:

- **Edge-type conductance**. `SpreadingActivation(edge_weights={...})` maps
  relation type → conductance. Conductive types include `supports`,
  `causes`, `implements`, `contains`, `extends`, `references`, `imports`,
  and `calls`. `contradicts` conducts too: contradiction is evidence, and
  suppressing it would hide conflicts from the sensory cortex. Unlisted
  types get `default_weight`.
- **Distance decay**. Pluggable `DecayFn` (hop distance → multiplier):
  `exponential_decay(rate)`, `harmonic_decay()`, `linear_decay(radius)`.
  Decay applies to *distance from the seed*, not compounded per wave. The
  raw (weight-product) energy propagates, and recorded activation is
  `raw × decay(hops)`. This rule keeps decay functions meaningful as
  specified curves. (`test_activation_decays_with_distance` caught a
  per-wave compounding bug; the invariant is now tested.)
- **Locality**. `threshold` prunes negligible energy; `max_hops` bounds the
  wave. A node keeps its maximum activation over all waves and seeds.
- Deterministic: sorted iteration, pure float functions of inputs.

`ExpansionPolicy` (reference: `ActivationFrontier`) turns the activation
field into a frontier: unvisited nodes above `min_activation`, best-first,
capped at `max_frontier`, optionally restricted to edge types.

## Convergence (`policies.py`)

Retrieval continues until a `ConvergencePolicy` fires. The trace records
the firing policy and its detail (`convergence` event). Implemented
policies:

| Policy | Stops when |
|---|---|
| `ConfidenceThreshold(t, k)` | ≥ k evidence items score ≥ t |
| `MinInformationGain(g)` | an iteration adds < g evidence mass |
| `GraphDiameter(n)` | the evidence graph reaches n nodes |
| `BudgetExhausted(key, limit)` | any engine-tracked budget (tokens, node visits) hits its limit |
| `MaxIterations(n)` | hard iteration cap |
| `AnyOf(p1, p2, …)` | first firing policy wins (order = preference in traces) |

`default_convergence()` = AnyOf(confidence, info-gain, diameter,
iterations). The combination stops early when evidence is strong, stops
when growth adds too little, and never runs unbounded. "Top-K" is
expressible as `AnyOf(GraphDiameter(k), MaxIterations(1))` — a degenerate
configuration, not the design center. The engine additionally stops on
`frontier_exhausted` when there is nothing left to expand.

## Speculative retrieval (`engine.py`)

`HypothesisManager.propose(query)` returns one or more `Hypothesis` lines.
The engine runs them concurrently (`asyncio.gather`) and merges only after
scoring (`EvidenceMerger`). The reference `BestScoreMerger` takes the
union with the best score per item, weighted by hypothesis prior. It keeps
provenance in the `"hypothesis"` channel. The engine never collapses a
hypothesis early; per-hypothesis evidence graphs remain available on
`RetrievalResult.hypotheses` for downstream arbitration.

## SGJM integration

The SGJM does **not** perform retrieval. It predicts likely missing
evidence, likely expansions, hidden relationships, and future states.
Those predictions enter the pipeline as `RetrievalHint`s on the `Query`
(`source="sgjm"`). Mechanically, hints with a text payload seed more
frontier queries in iteration 0. Hinted items still pass dense recall and
late-interaction scoring like everything else. Hints bias; they never
bypass.

The same mechanism serves the executive layer or any other component that
wants to steer perception without owning it.

## Observability

Every run emits a `RetrievalTrace`. The trace records hypothesis
proposals, per-iteration recall/rerank counts, activation field size, and
the expanded frontier (node ids). It also records evidence graph growth,
the merge decision summary, and the convergence reason. Events are
timestamped, JSON-serializable, and enough to replay or visualize a run
without re-executing models. Tests assert stage coverage
(`test_trace_records_every_stage`), so the trace cannot lose stages
silently.

## Open questions (future RFCs)

- Learned edge conductances: the dendritic training loop
  (docs/training-pipeline.md) produces exactly the per-relation utility
  statistics that should eventually *set* `edge_weights`. Using them would
  connect the world model's learned structure to the sensory cortex's
  search bias.
- Activation as prior vs. score: activation currently selects the frontier
  only. Whether it should also contribute a scoring channel needs
  empirical evidence from the testbed.
- Cross-hypothesis deduplication of retrieval work (shared frontier cache)
  without introducing synchronization between hypotheses.
