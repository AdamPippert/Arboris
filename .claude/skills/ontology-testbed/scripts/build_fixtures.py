#!/usr/bin/env python3
"""Build Arboris graph fixtures and masked-relation tasks from the catalogue.

Outputs (under tests/fixtures/ontology-playground/):
  fixtures.json   one graph fixture per catalogue ontology
  splits.json     deterministic train/dev/test assignment per fixture id
  tasks.json      masked-relation prediction tasks for dev and test fixtures
  manifest.json   catalogue sha256 + build parameters, for reproducibility

Everything is derived deterministically from the catalogue snapshot: splits
hash the fixture id, and distractor sampling is seeded per task. No RNG state
leaks between runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

DEFAULT_DIR = Path("tests/fixtures/ontology-playground")
MASK_FRACTION = 0.25          # fraction of edges masked per dev/test ontology
MIN_EDGES_TO_MASK = 3         # ontologies with fewer edges become train-only
N_DISTRACTORS = 9             # candidates per task = 1 true + 9 false pairs


def stable_hash(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")


def assign_split(fixture_id: str) -> str:
    bucket = stable_hash("arboris-split:" + fixture_id) % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "dev"
    return "test"


def to_fixture(entry: dict) -> dict | None:
    onto = entry.get("ontology") or {}
    etypes = onto.get("entityTypes") or []
    rels = onto.get("relationships") or []
    node_ids = {e["id"] for e in etypes if "id" in e}
    if len(node_ids) < 2:
        return None
    nodes = [
        {
            "id": e["id"],
            "name": e.get("name", e["id"]),
            "description": e.get("description", ""),
            "attributes": [
                {
                    "name": p.get("name"),
                    "type": p.get("type"),
                    "is_identifier": bool(p.get("isIdentifier")),
                }
                for p in e.get("properties", [])
            ],
        }
        for e in etypes
        if "id" in e
    ]
    edges = []
    for r in rels:
        if r.get("from") in node_ids and r.get("to") in node_ids:
            edges.append(
                {
                    "id": r.get("id") or f'{r["from"]}->{r["to"]}',
                    "source": r["from"],
                    "target": r["to"],
                    "relation": r.get("name", ""),
                    "cardinality": r.get("cardinality", ""),
                    "description": r.get("description", ""),
                }
            )
    return {
        "id": entry["id"],
        "name": entry.get("name", entry["id"]),
        "category": entry.get("category", "general"),
        "source": entry.get("source", "unknown"),
        "graph": {"nodes": nodes, "edges": edges},
    }


def make_tasks(fixture: dict, n_distractors: int) -> list[dict]:
    """Mask a deterministic subset of edges; build ranking candidates for each."""
    graph = fixture["graph"]
    edges = graph["edges"]
    # only edges marked maskable (default true) are eval targets; e.g. schema.org
    # subTypeOf edges stay in the graph as context but are never masked
    maskable_idx = [i for i, e in enumerate(edges) if e.get("maskable", True)]
    if len(maskable_idx) < MIN_EDGES_TO_MASK:
        return []
    rng = random.Random(stable_hash("arboris-mask:" + fixture["id"]))
    n_mask = max(1, round(len(maskable_idx) * MASK_FRACTION))
    masked_idx = set(rng.sample(maskable_idx, n_mask))
    masked = [edges[i] for i in sorted(masked_idx)]
    kept = [e for i, e in enumerate(edges) if i not in masked_idx]

    node_ids = [n["id"] for n in graph["nodes"]]
    true_pairs = {(e["source"], e["target"]) for e in edges}
    all_false = sorted(
        (a, b) for a in node_ids for b in node_ids if a != b and (a, b) not in true_pairs
    )

    partial_graph = {"nodes": graph["nodes"], "edges": kept}
    tasks = []
    for edge in masked:
        trng = random.Random(stable_hash(f'arboris-task:{fixture["id"]}:{edge["id"]}'))
        k = min(n_distractors, len(all_false))
        candidates = [{"source": edge["source"], "target": edge["target"]}] + [
            {"source": a, "target": b} for a, b in trng.sample(all_false, k)
        ]
        trng.shuffle(candidates)
        answer = next(
            i
            for i, c in enumerate(candidates)
            if c["source"] == edge["source"] and c["target"] == edge["target"]
        )
        tasks.append(
            {
                "fixture_id": fixture["id"],
                "task_id": f'{fixture["id"]}::{edge["id"]}',
                "graph": partial_graph,
                "candidates": candidates,
                "answer_index": answer,
                "masked_relation": edge["relation"],
            }
        )
    return tasks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="fixtures directory")
    ap.add_argument("--n-distractors", type=int, default=N_DISTRACTORS)
    args = ap.parse_args()

    cat_path = args.dir / "catalogue.json"
    if not cat_path.is_file():
        print(f"error: {cat_path} not found — run fetch_catalogue.py first", file=sys.stderr)
        return 1
    raw = cat_path.read_bytes()
    entries = json.loads(raw)["entries"]

    fixtures, skipped = [], 0
    for entry in entries:
        fx = to_fixture(entry)
        if fx is None:
            skipped += 1
            continue
        fixtures.append(fx)

    # merge fixtures from additional sources (e.g. schemaorg_fixtures.py);
    # each extra-fixtures-*.json is a list of fixture dicts in the same shape
    extra_counts = {}
    for extra_path in sorted(args.dir.glob("extra-fixtures-*.json")):
        extra = json.loads(extra_path.read_text())
        known = {fx["id"] for fx in fixtures}
        added = [fx for fx in extra if fx["id"] not in known and len(fx["graph"]["nodes"]) >= 2]
        fixtures.extend(added)
        extra_counts[extra_path.name] = len(added)

    splits: dict[str, str] = {}
    tasks: dict[str, list[dict]] = {"dev": [], "test": []}
    for fx in fixtures:
        # a fixture may pin its own split (e.g. schemaorg/full is train-only
        # because its edges overlap the schemaorg subtree fixtures)
        split = fx.get("split") or assign_split(fx["id"])
        n_maskable = sum(1 for e in fx["graph"]["edges"] if e.get("maskable", True))
        if split != "train" and n_maskable < MIN_EDGES_TO_MASK:
            split = "train"  # too few maskable edges to evaluate meaningfully
        splits[fx["id"]] = split
        if split in tasks:
            tasks[split].extend(make_tasks(fx, args.n_distractors))

    manifest = {
        "catalogue_sha256": hashlib.sha256(raw).hexdigest(),
        "n_fixtures": len(fixtures),
        "n_skipped": skipped,
        "extra_sources": extra_counts,
        "split_counts": {s: sum(1 for v in splits.values() if v == s) for s in ("train", "dev", "test")},
        "task_counts": {s: len(t) for s, t in tasks.items()},
        "mask_fraction": MASK_FRACTION,
        "n_distractors": args.n_distractors,
    }

    args.dir.mkdir(parents=True, exist_ok=True)
    for name, obj in [
        ("fixtures.json", fixtures),
        ("splits.json", splits),
        ("tasks.json", tasks),
        ("manifest.json", manifest),
    ]:
        (args.dir / name).write_text(json.dumps(obj, indent=1, sort_keys=True))
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
