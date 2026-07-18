#!/usr/bin/env python3
"""Fetch the Ontology-Playground catalogue and cache it locally.

The catalogue is the single JSON file the Ontology Playground web app loads:
https://microsoft.github.io/Ontology-Playground/catalogue.json

Deterministic by design: the snapshot is cached and its sha256 recorded, so
fixture builds are reproducible against a pinned snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

CATALOGUE_URL = "https://microsoft.github.io/Ontology-Playground/catalogue.json"
DEFAULT_OUT = Path("tests/fixtures/ontology-playground/catalogue.json")


def fetch(url: str, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "arboris-ontology-testbed"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="cache path for the catalogue snapshot")
    ap.add_argument("--refresh", action="store_true", help="re-download even if a cached snapshot exists")
    ap.add_argument("--cache-only", action="store_true", help="never touch the network; fail if no cache")
    args = ap.parse_args()

    override = os.environ.get("ONTOLOGY_CATALOGUE_PATH")
    if override:
        src = Path(override)
        if not src.is_file():
            print(f"error: ONTOLOGY_CATALOGUE_PATH={src} does not exist", file=sys.stderr)
            return 1
        raw = src.read_bytes()
    elif args.out.is_file() and not args.refresh:
        raw = args.out.read_bytes()
        print(f"using cached snapshot {args.out}")
    elif args.cache_only:
        print(f"error: no cached snapshot at {args.out} and --cache-only was given", file=sys.stderr)
        return 1
    else:
        print(f"fetching {CATALOGUE_URL} ...")
        raw = fetch(CATALOGUE_URL)

    cat = json.loads(raw)  # validate before caching
    entries = cat.get("entries", [])
    if not entries:
        print("error: catalogue has no entries — upstream format may have changed", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    print(f"catalogue: {len(entries)} entries, generatedAt={cat.get('generatedAt')}")
    print(f"sha256: {digest}")
    print(f"cached at: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
