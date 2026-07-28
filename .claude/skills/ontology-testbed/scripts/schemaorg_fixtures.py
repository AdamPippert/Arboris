#!/usr/bin/env python3
"""Convert the schema.org vocabulary into Arboris testbed fixtures.

Fetches the machine-readable schema.org release (JSON-LD) and converts it into
graph fixtures compatible with build_fixtures.py, which automatically merges
any extra-fixtures-*.json found in the fixtures directory.

Mapping (details: references/schemaorg-format.md):
  rdfs:Class                          -> nodes (entity types)
  rdf:Property, object-valued        -> edges (one per domain x range pair)
  rdf:Property, datatype-valued      -> attributes on the domain node
  rdfs:subClassOf                    -> "subTypeOf" edges + subtree partitioning

Schema.org is one connected vocabulary of ~1000 types, far larger than the
other testbed ontologies, so it is partitioned into subtree fixtures rooted at
the top-level children of schema:Thing, recursively split while larger than
--max-nodes. Superseded terms and the meta/attic sections are always excluded;
"pending" (unstable proposals) is excluded by default.

Deterministic: same release snapshot in -> byte-identical fixtures out.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

SCHEMAORG_URL = "https://schema.org/version/latest/schemaorg-current-https.jsonld"
DEFAULT_DIR = Path("tests/fixtures/ontology-playground")
DEFAULT_SECTIONS = "core,health-lifesci,bib,auto"
DATATYPE_ROOTS = {"schema:DataType"}


def ids(value) -> list[str]:
    """Normalize a JSON-LD ref or list of refs to a sorted list of @ids."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [value["@id"]] if "@id" in value else []
    if isinstance(value, list):
        out = []
        for v in value:
            out.extend(ids(v))
        return sorted(set(out))
    return [str(value)]


def section_of(node: dict) -> str:
    part = ids(node.get("schema:isPartOf"))
    if not part:
        return "core"
    return part[0].split("//")[-1].split(".")[0]  # e.g. "pending", "health-lifesci"


def label_of(node: dict) -> str:
    lbl = node.get("rdfs:label", "")
    if isinstance(lbl, dict):
        lbl = lbl.get("@value", "")
    return str(lbl) or node["@id"].split(":", 1)[-1]


def load_graph(path: Path) -> list[dict]:
    return json.loads(path.read_text())["@graph"]


def build_fixtures(graph: list[dict], sections: set[str], max_nodes: int, hierarchy: bool):
    keep = lambda n: (
        n["@id"].startswith("schema:")
        and "schema:supersededBy" not in n
        and section_of(n) in sections
    )
    def types_of(n: dict) -> list[str]:
        t = n.get("@type", [])
        return [t] if isinstance(t, str) else list(t)

    classes = {n["@id"]: n for n in graph if keep(n) and "rdfs:Class" in types_of(n)}
    # datatypes: schema:DataType roots plus anything whose subClassOf chain hits one
    datatypes = set(DATATYPE_ROOTS)
    changed = True
    while changed:
        changed = False
        for cid, c in classes.items():
            if cid not in datatypes and (
                "schema:DataType" in ids(c.get("@type")) or set(ids(c.get("rdfs:subClassOf"))) & datatypes
            ):
                datatypes.add(cid)
                changed = True
    entity_classes = {cid: c for cid, c in classes.items() if cid not in datatypes and cid != "schema:Thing"}

    parents = {cid: [p for p in ids(c.get("rdfs:subClassOf")) if p in entity_classes] for cid, c in entity_classes.items()}

    # --- partition assignment: walk each class up its (sorted, deterministic)
    # primary-parent chain to a child of Thing ------------------------------
    thing_children = sorted(
        cid for cid, c in entity_classes.items() if "schema:Thing" in ids(c.get("rdfs:subClassOf"))
    )

    def root_of(cid: str, seen=None) -> str:
        seen = seen or set()
        if cid in thing_children:
            return cid
        if cid in seen or not parents.get(cid):
            return "schema:_misc"
        seen.add(cid)
        return root_of(parents[cid][0], seen)

    assignment = {cid: root_of(cid) for cid in entity_classes}

    # recursively split oversized partitions at the partition root's children
    def subtree_members(part_root: str, members: list[str]) -> dict[str, list[str]]:
        groups = defaultdict(list)
        children = sorted(m for m in members if part_root in parents.get(m, []))
        for m in members:
            cur, seen = m, set()
            hop = None
            while cur != part_root and cur not in seen:
                seen.add(cur)
                nxt = parents.get(cur, [None])[0] if parents.get(cur) else None
                if nxt == part_root:
                    hop = cur
                    break
                cur = nxt or part_root
            groups[hop if hop in children else "__core__"].append(m)
        return groups

    partitions: dict[str, list[str]] = defaultdict(list)
    for cid, root in assignment.items():
        partitions[root].append(cid)
    final: dict[str, list[str]] = {}
    work = [(k.split(":", 1)[-1], sorted(v)) for k, v in partitions.items()]
    while work:
        name, members = work.pop()
        if len(members) <= max_nodes or name.count("/") >= 2:
            final[name] = members
            continue
        root_id = "schema:" + name.split("/")[-1]
        groups = subtree_members(root_id, [m for m in members if m != root_id])
        core = groups.pop("__core__", []) + ([root_id] if root_id in members else [])
        for child, sub in groups.items():
            if len(sub) < 3:
                core.extend(sub)
            else:
                work.append((f'{name}/{child.split(":", 1)[-1]}', sorted(sub)))
        if core:
            final[f"{name}/core"] = sorted(core)

    # --- properties -> edges & attributes ----------------------------------
    props = [n for n in graph if keep(n) and "rdf:Property" in types_of(n)]
    node_partition = {m: part for part, ms in final.items() for m in ms}

    attributes = defaultdict(list)
    edges_by_partition = defaultdict(list)
    n_cross, n_edges = 0, 0
    for p in sorted(props, key=lambda n: n["@id"]):
        domains = [d for d in ids(p.get("schema:domainIncludes")) if d in entity_classes]
        ranges = ids(p.get("schema:rangeIncludes"))
        dt_ranges = [r for r in ranges if r in datatypes or r == "schema:Thing"]
        obj_ranges = [r for r in ranges if r in entity_classes]
        name = label_of(p)
        for d in domains:
            if dt_ranges and not obj_ranges:
                attributes[d].append(
                    {"name": name, "type": dt_ranges[0].split(":", 1)[-1].lower(), "is_identifier": name == "identifier"}
                )
            for r in obj_ranges:
                n_edges += 1
                if node_partition.get(d) == node_partition.get(r):
                    edges_by_partition[node_partition[d]].append(
                        {
                            "id": f'{p["@id"].split(":", 1)[-1]}:{d.split(":", 1)[-1]}->{r.split(":", 1)[-1]}',
                            "source": d,
                            "target": r,
                            "relation": name,
                            "cardinality": "",
                            "description": str(p.get("rdfs:comment", ""))[:200],
                        }
                    )
                else:
                    n_cross += 1
    if hierarchy:
        for cid, ps in sorted(parents.items()):
            for par in ps:
                if node_partition.get(cid) == node_partition.get(par):
                    edges_by_partition[node_partition[cid]].append(
                        {
                            "id": f'subTypeOf:{cid.split(":", 1)[-1]}->{par.split(":", 1)[-1]}',
                            "source": cid,
                            "target": par,
                            "relation": "subTypeOf",
                            "cardinality": "many-to-one",
                            "description": "rdfs:subClassOf in the schema.org type hierarchy",
                            # hierarchy edges are context, not eval targets: they
                            # dominate edge counts and their hub parents make them
                            # trivially degree-predictable, which would skew the
                            # benchmark toward one easy relation
                            "maskable": False,
                        }
                    )

    fixtures = []
    for part in sorted(final):
        members = final[part]
        nodes = [
            {
                "id": cid,
                "name": label_of(entity_classes[cid]),
                "description": str(entity_classes[cid].get("rdfs:comment", ""))[:200],
                "attributes": sorted(attributes.get(cid, []), key=lambda a: a["name"]),
            }
            for cid in sorted(members)
        ]
        edges = sorted(edges_by_partition.get(part, []), key=lambda e: e["id"])
        if len(nodes) >= 2 and edges:
            fixtures.append(
                {
                    "id": f"schemaorg/{part.lower()}",
                    "name": f"schema.org — {part}",
                    "category": "schemaorg",
                    "source": "external",
                    "graph": {"nodes": nodes, "edges": edges},
                }
            )
    # one full-vocabulary fixture, pinned to the train split: subtree
    # partitioning drops cross-partition property edges (the majority — most
    # schema.org properties connect across top-level subtrees), so this fixture
    # ensures every property edge still reaches implementations during fit().
    # Leakage guard: edges belonging to subtree fixtures bound for dev/test are
    # excluded here, otherwise their masked eval edges would be visible in
    # training via this fixture.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_fixtures as _bf  # same directory; reuse the split function

    # held out by (source, target) PAIR, not edge id: parallel properties on
    # the same endpoints (author/creator on CreativeWork->Person) would
    # otherwise leak the masked pair into training as correlated signal
    held_out_pairs = set()
    for f in fixtures:
        n_maskable = sum(1 for e in f["graph"]["edges"] if e.get("maskable", True))
        if n_maskable >= _bf.MIN_EDGES_TO_MASK and _bf.assign_split(f["id"]) != "train":
            held_out_pairs.update(
                (e["source"], e["target"]) for e in f["graph"]["edges"] if e.get("maskable", True)
            )

    all_edges = []
    for p in sorted(props, key=lambda n: n["@id"]):
        domains = [d for d in ids(p.get("schema:domainIncludes")) if d in entity_classes]
        obj_ranges = [r for r in ids(p.get("schema:rangeIncludes")) if r in entity_classes]
        for d in domains:
            for r in obj_ranges:
                if (d, r) in held_out_pairs:
                    continue
                all_edges.append(
                    {
                        "id": f'{p["@id"].split(":", 1)[-1]}:{d.split(":", 1)[-1]}->{r.split(":", 1)[-1]}',
                        "source": d,
                        "target": r,
                        "relation": label_of(p),
                        "cardinality": "",
                        "description": str(p.get("rdfs:comment", ""))[:200],
                    }
                )
    fixtures.append(
        {
            "id": "schemaorg/full",
            "name": "schema.org — full vocabulary",
            "category": "schemaorg",
            "source": "external",
            "split": "train",
            "graph": {
                "nodes": [
                    {
                        "id": cid,
                        "name": label_of(entity_classes[cid]),
                        "description": str(entity_classes[cid].get("rdfs:comment", ""))[:200],
                        "attributes": sorted(attributes.get(cid, []), key=lambda a: a["name"]),
                    }
                    for cid in sorted(entity_classes)
                ],
                "edges": sorted(all_edges, key=lambda e: e["id"]),
            },
        }
    )

    stats = {
        "n_classes": len(entity_classes),
        "n_properties": len(props),
        "n_object_edges": n_edges,
        "n_cross_partition_dropped": n_cross,
        "n_fixtures": len(fixtures),
    }
    return fixtures, stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--max-nodes", type=int, default=60, help="split subtrees larger than this")
    ap.add_argument("--sections", default=DEFAULT_SECTIONS, help="comma list; add 'pending' for unstable terms")
    ap.add_argument("--no-hierarchy", action="store_true", help="omit subTypeOf edges")
    ap.add_argument("--refresh", action="store_true", help="re-download the release snapshot")
    args = ap.parse_args()

    snap = args.dir / "schemaorg-current.jsonld"
    if not snap.is_file() or args.refresh:
        print(f"fetching {SCHEMAORG_URL} ...")
        req = urllib.request.Request(SCHEMAORG_URL, headers={"User-Agent": "arboris-ontology-testbed"})
        snap.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(req, timeout=60) as resp:
            snap.write_bytes(resp.read())
    raw = snap.read_bytes()
    graph = json.loads(raw)["@graph"]

    fixtures, stats = build_fixtures(
        graph, set(args.sections.split(",")), args.max_nodes, hierarchy=not args.no_hierarchy
    )
    out = args.dir / "extra-fixtures-schemaorg.json"
    out.write_text(json.dumps(fixtures, indent=1, sort_keys=True))
    stats["snapshot_sha256"] = hashlib.sha256(raw).hexdigest()
    stats["out"] = str(out)
    print(json.dumps(stats, indent=2))
    print("now re-run build_fixtures.py to merge, split, and generate tasks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
