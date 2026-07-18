# Ontology-Playground catalogue format

Source: `https://microsoft.github.io/Ontology-Playground/catalogue.json` — the
single JSON file the [Ontology Playground](https://github.com/microsoft/Ontology-Playground)
web app loads for its gallery. Snapshot observed 2026-06-19: 71 entries.

## Top level

```json
{ "generatedAt": "ISO timestamp", "count": 71, "entries": [ ... ] }
```

## Entry

| Field | Notes |
|---|---|
| `id` | e.g. `official/cosmic-coffee`, `community/...`, `external/fibo-...` |
| `name`, `description`, `icon` | display metadata |
| `category` | observed: retail, school, finance, healthcare, manufacturing, education, food, general, technology, fibo, media, events |
| `tags` | free-form strings |
| `source` | `official` (44), `community` (17), `external` (10) |
| `ontology` | the actual graph — below |

## Ontology object

```json
{
  "name": "...", "description": "...",
  "entityTypes": [
    { "id": "customer", "name": "Customer", "description": "...",
      "icon": "👤", "color": "#...",
      "properties": [
        { "name": "customerId", "type": "string", "isIdentifier": true,
          "unit": "USD (optional)", "description": "..." } ] }
  ],
  "relationships": [
    { "id": "customer_places_order", "name": "places",
      "from": "customer", "to": "order",
      "cardinality": "one-to-many | many-to-one | one-to-one | many-to-many",
      "description": "...",
      "attributes": [ { "name": "quantity", "type": "integer" } ] }
  ]
}
```

`from`/`to` reference `entityTypes[].id`. `build_fixtures.py` drops
relationships whose endpoints don't resolve and skips ontologies with <2
entity types.

## Mapping to Arboris fixtures

| Catalogue | Fixture |
|---|---|
| `entityTypes[]` | `graph.nodes[]` (id, name, attribute schema) |
| `relationships[]` | `graph.edges[]` (source, target, relation, cardinality) |
| entry `id`/`category`/`source` | fixture provenance fields |

Note these are **schema-level** graphs (entity *types* and their relations),
not instance data — the testbed evaluates relational-structure inference, not
instance dynamics. Statistics at the 2026-06-19 snapshot: ~6.7 entity types
and ~7.3 relationships per ontology (1–28 relationships).

## Licensing / provenance

The Ontology-Playground repository is Microsoft open source (see its GitHub
repo for exact license). The testbed **fetches at use time and does not
vendor** catalogue content into the Arboris repo; fixtures live under
`tests/fixtures/ontology-playground/` which is gitignored. If catalogue data
is ever redistributed (e.g. in the Arboris open dataset), it must first pass
the provenance gate in `docs/data-pipeline.md`.
