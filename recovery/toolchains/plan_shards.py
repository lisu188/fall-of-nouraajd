#!/usr/bin/env python3
"""Keep exhaustive historical validation below GitHub's matrix size limit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def planShards(catalog: dict, trees_per_shard: int = 16) -> dict:
    if trees_per_shard < 1:
        raise ValueError("trees_per_shard must be positive")
    trees = catalog["trees"]
    expected = catalog["summary"]["damagedTreeCount"]
    identities = {tree["tree"] for tree in trees}
    if not trees or len(trees) != expected or len(identities) != len(trees):
        raise ValueError("Catalog must contain each damaged tree exactly once")
    count = (len(trees) + trees_per_shard - 1) // trees_per_shard
    if count > 256:
        raise ValueError("Recovery matrix exceeds GitHub's 256-job limit")
    return {"include": [{"index": index, "count": count} for index in range(count)]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("recovery/catalog.json"))
    parser.add_argument("--trees-per-shard", type=int, default=16)
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text())
    print(json.dumps(planShards(catalog, args.trees_per_shard), separators=(",", ":")))


if __name__ == "__main__":
    main()
