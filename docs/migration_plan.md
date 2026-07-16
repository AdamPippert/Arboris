# Arboris migration plan

## Strategy

Evolve the existing seed incrementally. Preserve the `src/arboris` package, version
API, license, notice, and honest pre-alpha positioning. Add small ablatable modules;
do not introduce transformer downloads, external services, planning, large memory
packs, or structural self-modification before the local predictive slice works.

## Adapted target tree

Only useful files are created at each stage.

```text
.
├── configs/{base,datasets,models,training,evaluation,personas,experiments}/
├── data/{raw,staged,canonical,validated,compiled,splits,manifests}/
├── docs/
├── experiments/{definitions,runs,reports,leaderboards}/
├── ontologies/{upper,reasoning,domains,personas,shapes,versions}/
├── src/arboris/
│   ├── core/                 # types, protocols, registry, errors
│   ├── graph/                # schema, snapshots, mutation, diff, serialization
│   ├── ontology/             # version loading, constraints, migration
│   ├── simulation/           # deterministic infrastructure world
│   ├── data/                 # manifests, compilation, splits
│   ├── dendritic/            # branches, soma, router, diagnostics
│   ├── prediction/           # encoders, EMA target, predictor, hypotheses
│   ├── arbitration/          # explicit configurable scoring
│   ├── memory/               # repository protocols and later implementations
│   ├── models/               # assembly and baselines
│   ├── training/             # bounded loops and checkpoints
│   ├── evaluation/           # graph/calibration/efficiency metrics
│   └── cli/                  # independent operational entry points
└── tests/{unit,property,integration,regression,training,end_to_end}/
```

Using `src/arboris` is the sole intentional difference from the illustrative tree;
it preserves current packaging and avoids duplicate import roots.

## Component reuse map

| Existing component | Action | Reason |
|---|---|---|
| `src/arboris/__init__.py` | Preserve and extend cautiously | Only existing public API. |
| `pyproject.toml` | Extend | Keep setuptools; declare runtime/dev tools and CLI. |
| `README.md` | Revise incrementally | Accurate status and identity; needs executable quickstart. |
| `LICENSE`, `NOTICE` | Preserve verbatim | Already suitable. |
| `.gitignore` | Extend when artifacts exist | Current entries are useful. |
| `error.log` | Ignore | Untracked user file, not migration input. |

## Stages and acceptance gates

1. **Stabilize and graph foundation (smallest coherent stage).** Add dependencies,
   canonical Pydantic records, provenance hashing, immutable snapshots, reversible
   mutations, graph diffing, ontology documents/validator, and tests. Gate: clean
   install; deterministic serialization; mutation rollback reconstructs the source;
   illegal relations fail with actionable issues.
2. **Deterministic infrastructure data.** Add one cluster/two nodes/two pods/service/
   route world; delete-pod, cordon-node, remove-route interventions; versioned
   manifests; Parquet and Kuzu inspection. Gate: one command emits identical records
   for identical seed, with complete provenance and zero validation errors.
3. **Dendritron and hypotheses.** Add registry-driven branches, sparse gates, soma,
   typed confidence/uncertainty, two deterministic candidate futures, and arbitrator.
   Gate: diagnostics show active branches and arbitrator selects or abstains.
4. **Predictive baseline.** Add tensor compiler, relational baseline, action-conditioned
   predictor, tiny overfit loop, metrics, bounded checkpoint and reload equivalence.
5. **SGJM/JEPA.** Add context and EMA target encoders, latent objective and collapse
   diagnostics; compare against the stronger non-JEPA baseline.
6. **Routing, packs, and expansion.** Only after transition evidence: memory-pack
   contracts, ontology-aware router, speculative rollout, then persona interfaces.

## First ten executable work items

| ID | Work item | Test / acceptance criterion |
|---|---|---|
| W001 | Lock packaging and tooling | Clean `uv sync --extra dev`; import and CLI help succeed. Neural stages install the platform-specific `model` extra. |
| W002 | Canonical schemas and stable IDs | Valid records round-trip; invalid confidence/time fails. |
| W003 | Provenance hashing | Same bytes yield same SHA-256 identity; changed bytes do not. |
| W004 | Upper/infrastructure ontology v0.1 | Documents load; all simulator types/relations are declared. |
| W005 | Constraint validator | Domain/range, dangling endpoint, required property, duplicate ID, exclusive state tests pass. |
| W006 | Snapshot diff/mutations/rollback | Applying a diff reconstructs target; inverse reconstructs source. |
| W007 | Deterministic simulator | Same seed/intervention produces byte-identical episode. |
| W008 | Versioned dataset and stores | Parquet rows/readback and Kuzu counts equal manifest counts. |
| W009 | Dendritron/arbitration slice | Multiple branches and candidates; weights/diagnostics exposed; select/abstain covered. |
| W010 | Tiny baseline experiment | Loss decreases, baseline reported, checkpoint reload max delta is within tolerance. |

## First vertical-slice experiment

`VS001-infrastructure-next-state` uses the deterministic infrastructure world. Input
is a typed observation graph plus one of delete-pod, cordon-node, or remove-route.
Object, topology, temporal, causal, context, and action branches process explicit
features. A latent predictor proposes at least two next-state deltas. Ontology
validation supplies consistency penalties, and the arbitrator selects or abstains.

The primary baseline is intervention-frequency prediction. Report training loss,
node-state and edge-change F1, calibration, active branches, parameters, runtime,
and checkpoint reload delta. The experiment is evidence only for plumbing on the
tiny training set; it cannot support generalization claims.

## Decisions made and approval boundaries

- Infrastructure is the initial synthetic world, reconciling both briefs.
- Structured observations precede transformer perception.
- Pydantic represents persisted records; dataclasses may represent tensor-bearing
  runtime values because tensors are not canonical storage.
- Kuzu and Parquet are integration dependencies; unit tests remain service-free.
- `src/` packaging is preserved.

Explicit approval is required before remote pushes, large model/data downloads,
GPU-expensive training, destructive migration, or changing the license. No such
action is part of these stages.

## Complexity and risks

Stages 1–2 are low-to-moderate complexity; 3–4 are moderate; JEPA, learned routing,
and multi-horizon speculation are research-high complexity. Main risks are leakage
from near-identical simulator worlds, mistaking ontology rules for learned beliefs,
and drawing claims from overfit demonstrations. Split controls, explicit rule types,
and falsification ledgers mitigate these risks.
