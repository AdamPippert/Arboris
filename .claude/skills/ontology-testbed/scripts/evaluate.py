#!/usr/bin/env python3
"""Evaluate an Arboris implementation on the masked-relation testbed.

An implementation is a class exposing:

    fit(train_fixtures: list[dict]) -> None
    score_edge(graph: dict, source: str, target: str) -> float

Select it with --impl:
    --impl random                    builtin floor baseline
    --impl degree                    builtin structural baseline
    --impl mypkg.mymodule:MyClass    any importable adapter class

Metrics: hits@1 (ties count as failure) and MRR, aggregate and per-category.
A JSON report is written next to the fixtures.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_DIR = Path("tests/fixtures/ontology-playground")


class RandomBaseline:
    """Deterministic pseudo-random scores — the floor (~1/n_candidates hits@1)."""

    def fit(self, train_fixtures):
        pass

    def score_edge(self, graph, source, target):
        digest = hashlib.sha256(f"random:{source}->{target}".encode()).digest()
        return int.from_bytes(digest[:8], "big") / 2**64


class DegreeBaseline:
    """Score pairs by connectivity in the partial graph plus a relation prior
    learned from training fixtures (how often a node-name pair co-occurs as an
    edge anywhere in training). Simple, but a real model must beat it."""

    def fit(self, train_fixtures):
        self.pair_prior = defaultdict(int)
        for fx in train_fixtures:
            for e in fx["graph"]["edges"]:
                self.pair_prior[(e["source"], e["target"])] += 1

    def score_edge(self, graph, source, target):
        out_deg = sum(1 for e in graph["edges"] if e["source"] == source)
        in_deg = sum(1 for e in graph["edges"] if e["target"] == target)
        prior = self.pair_prior.get((source, target), 0)
        return (out_deg + 1) * (in_deg + 1) + 10.0 * prior


BUILTINS = {"random": RandomBaseline, "degree": DegreeBaseline}


def load_impl(spec: str):
    if spec in BUILTINS:
        return BUILTINS[spec]()
    if ":" not in spec:
        raise SystemExit(f"--impl must be a builtin {sorted(BUILTINS)} or 'module:Class', got {spec!r}")
    mod_name, cls_name = spec.split(":", 1)
    cls = getattr(importlib.import_module(mod_name), cls_name)
    return cls()


def evaluate(impl, tasks: list[dict]) -> dict:
    per_category = defaultdict(lambda: {"n": 0, "hits1": 0, "rr_sum": 0.0})
    for t in tasks:
        scores = [
            impl.score_edge(t["graph"], c["source"], c["target"]) for c in t["candidates"]
        ]
        true_score = scores[t["answer_index"]]
        # rank = 1 + number of candidates strictly better + ties (ties = failure)
        better_or_tied = sum(
            1 for i, s in enumerate(scores) if i != t["answer_index"] and s >= true_score
        )
        rank = 1 + better_or_tied
        cat = t.get("category", "general")
        for key in ("__all__", cat):
            b = per_category[key]
            b["n"] += 1
            b["hits1"] += 1 if rank == 1 else 0
            b["rr_sum"] += 1.0 / rank
    return {
        cat: {
            "n_tasks": b["n"],
            "hits@1": round(b["hits1"] / b["n"], 4),
            "mrr": round(b["rr_sum"] / b["n"], 4),
        }
        for cat, b in sorted(per_category.items())
        if b["n"]
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--impl", default="degree", help="builtin name or module:Class spec")
    ap.add_argument("--split", choices=("dev", "test"), default="dev")
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = ap.parse_args()

    for req in ("fixtures.json", "splits.json", "tasks.json"):
        if not (args.dir / req).is_file():
            print(f"error: {args.dir / req} missing — run build_fixtures.py first", file=sys.stderr)
            return 1

    fixtures = json.loads((args.dir / "fixtures.json").read_text())
    splits = json.loads((args.dir / "splits.json").read_text())
    tasks = json.loads((args.dir / "tasks.json").read_text())[args.split]
    if not tasks:
        print(f"error: no tasks in split {args.split!r}", file=sys.stderr)
        return 1

    category_of = {fx["id"]: fx["category"] for fx in fixtures}
    for t in tasks:
        t["category"] = category_of.get(t["fixture_id"], "general")

    train = [fx for fx in fixtures if splits.get(fx["id"]) == "train"]
    impl = load_impl(args.impl)
    impl.fit(train)
    results = evaluate(impl, tasks)

    report = {
        "impl": args.impl,
        "split": args.split,
        "n_train_fixtures": len(train),
        "results": results,
    }
    out = args.dir / f"report-{args.impl.replace(':', '_').replace('.', '_')}-{args.split}.json"
    out.write_text(json.dumps(report, indent=1, sort_keys=True))

    agg = results["__all__"]
    print(f"impl={args.impl} split={args.split} tasks={agg['n_tasks']}")
    print(f"  hits@1 = {agg['hits@1']:.4f}   mrr = {agg['mrr']:.4f}")
    print("  per category:")
    for cat, r in results.items():
        if cat != "__all__":
            print(f"    {cat:15s} n={r['n_tasks']:<4d} hits@1={r['hits@1']:.4f} mrr={r['mrr']:.4f}")
    print(f"report written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
