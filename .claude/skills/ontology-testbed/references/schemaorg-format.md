# schema.org corpus

Source: the machine-readable schema.org release,
`https://schema.org/version/latest/schemaorg-current-https.jsonld` (~1.5 MB
JSON-LD). Snapshot observed 2026-07: 1,010 `rdfs:Class` and 1,676
`rdf:Property` terms across the core vocabulary and section extensions
(`pending`, `health-lifesci`, `bib`, `auto`, `meta`).

`scripts/schemaorg_fixtures.py` converts it into testbed fixtures
(`extra-fixtures-schemaorg.json`), which `build_fixtures.py` merges
automatically.

## Mapping

| schema.org | Fixture |
|---|---|
| `rdfs:Class` (non-datatype, not superseded) | node |
| `rdf:Property` with object-typed `rangeIncludes` | one edge per (domain, range) pair, relation = property label |
| `rdf:Property` with only datatype ranges (Text, Number, Date, …) | attribute on each domain node |
| `rdfs:subClassOf` | `subTypeOf` edges (**`maskable: false`**) + subtree partitioning |

The converter drops terms with `schema:supersededBy`. It always excludes the
`meta`/attic sections. It excludes `pending` (unstable proposals) by default
(`--sections core,health-lifesci,bib,auto`, add `pending` to opt in).
It also excludes `schema:Thing` itself: the type connects to nearly
everything and would be a degenerate hub.

## Why subTypeOf edges are never masked

Hierarchy edges dominate raw edge counts: in the 2026-07 snapshot, ~90% of
naively masked schema.org tasks were `subTypeOf`. Their targets are hub
parents, which a degree heuristic predicts almost trivially. They stay in
the graphs as relational context but are never eval targets, so schema.org
tasks measure property-relation inference.

## Partitioning and the full fixture

schema.org is one connected vocabulary, so the converter partitions it into
subtree fixtures rooted at the children of `Thing` (Person, Place,
CreativeWork, Event, MedicalEntity, …). It recursively splits subtrees above
`--max-nodes` (default 60).

Most property edges cross subtree boundaries (CreativeWork→Person,
Event→Place, …) and are dropped from subtree fixtures — the manifest records
the count. To keep that training signal, the converter also emits
**`schemaorg/full`**: the entire vocabulary as a single fixture pinned to
`"split": "train"`.

**Leakage guard:** if a (source, target) pair appears as a maskable edge in
a subtree fixture assigned to dev/test, `schemaorg/full` excludes that pair.
The exclusion works by endpoint pair, not edge id. Parallel properties on
the same endpoints (e.g. `author` and `creator`, both CreativeWork→Person)
therefore cannot leak the answer into training. The guard computes the split
assignment with the same hash function `build_fixtures.py` uses, so the
guard and the actual split cannot drift apart.

## Role in the testbed

schema.org is primarily **training enrichment**: it multiplies training
graphs and contributes a web-scale, professionally curated vocabulary with
rich attribute schemas. It contributes only a few eval tasks, because
coherent subgraphs with ≥3 within-partition property edges are rare. The
Ontology-Playground catalogue remains the eval core.

## Licensing / provenance

schema.org vocabulary content is © the schema.org Community Group /
sponsors, licensed **CC BY-SA 3.0** (share-alike). The testbed fetches at use
time and does not vendor the release into the Arboris repo; fixtures are
gitignored. If schema.org-derived data is redistributed (e.g. inside the
Arboris open dataset), it must pass the provenance gate in
`docs/data-pipeline.md`, carry attribution, and respect share-alike terms.
CC BY-SA is a different license family than the repo's Apache-2.0, so keep
derived data clearly separated from code.
