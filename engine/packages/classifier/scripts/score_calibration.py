"""Merges a `build_calibration_sample.py` candidate file with Hansel's own
hand-labels (a JSON object {"_id": true|false}) and reports precision per
band -- the number `calibration.py`'s measured tables get filled in from.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates", type=Path)
    ap.add_argument("labels", type=Path)
    ap.add_argument("--band-key", default="band")
    args = ap.parse_args()

    labels = {int(k): v for k, v in json.loads(args.labels.read_text(encoding="utf-8")).items()}
    with open(args.candidates, encoding="utf-8") as fh:
        rows = [json.loads(l) for l in fh if l.strip()]

    by_band: dict[str, list[bool]] = defaultdict(list)
    missing = 0
    for r in rows:
        _id = r["_id"]
        if _id not in labels:
            missing += 1
            continue
        by_band[r[args.band_key]].append(labels[_id])

    print(f"{len(rows)} candidates, {missing} unlabelled")
    for band in sorted(by_band, key=lambda b: -len(by_band[b])):
        vals = by_band[band]
        n_true = sum(vals)
        n = len(vals)
        prec = n_true / n if n else float("nan")
        print(f"  {band:14s} n={n:3d}  true={n_true:3d}  precision={prec:.3f}  ship={'YES' if prec >= 0.80 else 'no'}")


if __name__ == "__main__":
    main()
