"""Step 1 of the calibration pipeline: build the sampling frame from both
cities' live classifier output, draw the stratified sample, write it to
`data/calibration/sample.jsonl`.

One row per (city, wp_id, facet) sampling unit -- but because `type` and
`format` are scored independently, the same article can be selected once for
its `type` cell and separately for its `format` cell. The LLM-labelling step
(`llm_client.py`) groups by (city, wp_id) and makes exactly one blind call
per *article*, asking for both facets at once, and applies the result to
however many sample rows that article satisfies -- one call never means one
row.
"""
from __future__ import annotations

import json
from pathlib import Path

from .db_frame import build_sampling_frame
from .strata import FrameRecord, stratified_sample


def build_and_sample(root: Path, seed: str = "now-eval-calibration-v1") -> list[dict]:
    from now_platform_db.settings import platform_database_url
    from sqlalchemy import create_engine

    from .db_frame import _load_term_map

    term_map = _load_term_map(create_engine(platform_database_url()))

    frame_by_key: dict[str, dict] = {}
    all_records: list[FrameRecord] = []
    for city in ("jakarta", "bali"):
        frame = build_sampling_frame(city, root, term_map)
        for row in frame:
            frame_by_key[row["key"]] = row
            all_records.append(
                FrameRecord(
                    key=row["key"],
                    city=row["city"],
                    facet=row["facet"],
                    proposed_value=row["proposed_value"],
                    confidence=row["confidence"],
                )
            )

    selected = stratified_sample(all_records, seed=seed)
    return [frame_by_key[r.key] for r in selected]


def write_sample(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def summarize(rows: list[dict]) -> dict:
    from collections import Counter

    by_cell = Counter((r["city"], r["facet"], round(r["confidence"], 2)) for r in rows)
    unique_articles = {(r["city"], r["wp_id"]) for r in rows}
    return {
        "total_rows": len(rows),
        "unique_articles": len(unique_articles),
        "cells": {f"{c}:{f}:{v}": n for (c, f, v), n in sorted(by_cell.items())},
    }
