# RFC-0002: Dendritic activation, convergence, speculation, and SGJM hints

**Status:** Implemented (reference implementation) · relates to ADR-0001

## Dendritic activation (`activation.py`)

The dendritic fabric decides *where retrieval looks next*. Instead of
uniform traversal, evidence nodes inject activation energy that spreads
along edges:

- **Edge-type conductance.** `SpreadingActivation(edge_weights={...})` maps
  relation type → conductance. `supports`, `causes`, `implements`,
  `contains`, `extends`, `references`, `imports`, `calls` — and
  `contradicts`, which conducts too: contradiction is evidence, suppressing
  it would blind the sensory cortex. Unlisted types get `default_weight`.
- **Distance decay.** Pluggable `DecayFn` (hop distance → multiplier):
  `exponential_decay(rate)`, `harmonic_decay()`, `linear_decay(radius)`.
  Decay applies to *distance from the seed*, not compounded per wave — the
  raw (weight-product) energy propagates, and recorded activation is
  `raw × decay(hops)`. This keeps decay functions meaningful as specified
  curves. (A per-wave compounding bug was caught by
  `test_activation_decays_with_distance`; the invariant is now tested.)
- **Locality.** `threshold` prunes negligible energy; `max_hops` bounds the
  wave. A node keeps its maximum activation over all waves and seeds.
- Deterministic: sorted iteration, pure float functions of inputs.

`ExpansionPolicy` (reference: `ActivationFrontier`) turns the activation
field into a frontier: unvisited nodes above `min_activation`, best-first,
capped at `max_frontier`, optionally restricted to edge types.

## Convergence (`policies.py`)

Retrieval continues until a `ConvergencePolicy` fires, and the firing policy
plus its detail are recorded in the trace (`convergence` event). Implemented
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
iterations): stop early when evidence is strong, stop when growth stops
paying, never run away. "Top-K" is expressible as
`AnyOf(GraphDiameter(k), MaxIterations(1))` — a degenerate configuration,
not the design center. The engine additionally stops on `frontier_exhausted`
when there is nothing left to expand.

## Speculative retrieval (`engine.py`)

`HypothesisManager.propose(query)` returns one or more `Hypothesis` lines;
the engine runs them concurrently (`asyncio.gather`) and merges only after
scoring (`EvidenceMerger`; reference `BestScoreMerger` = union, best score
per item, weighted by hypothesis prior, provenance kept in the
`"hypothesis"` channel). No hypothesis is collapsed early; per-hypothesis
evidence graphs remain available on `RetrievalResult.hypotheses` for
downstream arbitration.

## SGJM integration

The SGJM (Arboris's predictive world model) does **not** perform retrieval.
It predicts — likely missing evidence, likely expansions, hidden
relationships, future states — and those predictions enter the pipeline as
`RetrievalHint`s on the `Query` (`source="sgjm"`). Mechanically, hints with
a text payload seed additional frontier queries in iteration 0; hinted
items still pass dense recall and late-interaction scoring like everything
else. Hints bias, they never bypass. The same mechanism serves the
executive layer or any other component that wants to steer perception
without owning it.

## Observability

Every run emits a `RetrievalTrace`: hypothesis proposals, per-iteration
recall/rerank counts, activation field size, expanded frontier (node ids),
evidence graph growth, merge decision summary, and the convergence reason.
Events are timestamped, JSON-serializable, and sufficient to replay or
visualize a run without re-executing models. Tests assert stage coverage
(`test_trace_records_every_stage`) so the trace cannot silently rot.

## Open questions (future RFCs)

- Learned edge conductances: the dendritic training loop
  (docs/training-pipeline.md) produces exactly the per-relation utility
  statistics that should eventually *set* `edge_weights` — closing the loop
  between the world model's learned structure and the sensory cortex's
  search bias.
- Activation as prior vs. score: currently activation selects the frontier
  only; whether it should also contribute a scoring channel needs empirical
  evidence from the testbed.
- Cross-hypothesis deduplication of retrieval work (shared frontier cache)
  without introducing synchronization between hypotheses.
