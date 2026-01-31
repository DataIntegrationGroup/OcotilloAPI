#!/usr/bin/env python3
"""Report WaterLevels.csv MeasuredBy values missing from measured_by_mapper.json."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / "transfers" / "data" / "nma_csv_cache"
MAPPER_PATH = REPO_ROOT / "transfers" / "data" / "measured_by_mapper.json"
WATERLEVELS_PATH = CACHE_DIR / "WaterLevels.csv"


def load_mapper() -> set[str]:
    with MAPPER_PATH.open() as f:
        mapper = json.load(f)
    return set(mapper.keys())


def collect_missing(map_keys: set[str]) -> Counter[str]:
    missing = Counter()
    if not WATERLEVELS_PATH.exists():
        raise FileNotFoundError(f"Missing WaterLevels.csv at {WATERLEVELS_PATH}")

    with WATERLEVELS_PATH.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        if "MeasuredBy" not in reader.fieldnames:
            raise ValueError("MeasuredBy column not found in WaterLevels.csv")
        for row in reader:
            value = (row.get("MeasuredBy") or "").strip()
            if not value:
                continue
            if value not in map_keys:
                missing[value] += 1
    return missing


def main() -> None:
    mapper_keys = load_mapper()
    missing_counts = collect_missing(mapper_keys)

    if not missing_counts:
        print("All MeasuredBy values are covered by measured_by_mapper.json")
        return

    print("MeasuredBy values missing from mapper (value -> count):")
    for value, count in missing_counts.most_common():
        print(f"  {value}: {count}")


if __name__ == "__main__":
    main()
