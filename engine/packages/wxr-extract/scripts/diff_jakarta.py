#!/usr/bin/env python
"""Compare the WXR-derived Jakarta extraction against the existing
MariaDB-dump-derived one, joined by wp_id. Read-only: only reads
jakarta/content/extracted/*.jsonl (dump) and
jakarta/content/extracted-wxr/*.jsonl (WXR); writes nothing there.

Usage:
    python scripts/diff_jakarta.py [--dump-dir jakarta/content/extracted] \
        [--wxr-dir jakarta/content/extracted-wxr]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def by_wp_id(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {r["wp_id"]: r for r in rows if "wp_id" in r}


ARTICLE_FIELDS = [
    "title", "slug", "status", "date", "modified", "author_id",
    "permalink", "categories", "tags", "thumbnail_id", "content_html", "meta",
]


def diff_articles(dump: list[dict], wxr: list[dict]) -> dict[str, Any]:
    d = by_wp_id(dump)
    w = by_wp_id(wxr)
    dump_ids, wxr_ids = set(d), set(w)
    only_dump = sorted(dump_ids - wxr_ids)
    only_wxr = sorted(wxr_ids - dump_ids)
    both = sorted(dump_ids & wxr_ids)

    field_mismatches: dict[str, list[dict[str, Any]]] = {f: [] for f in ARTICLE_FIELDS}
    for wp_id in both:
        dr, wr = d[wp_id], w[wp_id]
        for f in ARTICLE_FIELDS:
            dv, wv = dr.get(f), wr.get(f)
            if f == "categories":
                # Order-sensitive difference is expected (see extract.py
                # docstring: WXR can't replicate primary-category
                # reordering) — report separately as "same set, different
                # order" vs a genuine set difference.
                if dv == wv:
                    continue
                if isinstance(dv, list) and isinstance(wv, list) and sorted(dv) == sorted(wv):
                    field_mismatches[f].append({"wp_id": wp_id, "kind": "order_only", "dump": dv, "wxr": wv})
                else:
                    field_mismatches[f].append({"wp_id": wp_id, "kind": "set_diff", "dump": dv, "wxr": wv})
                continue
            if f == "meta":
                if dv == wv:
                    continue
                keys = set(dv or {}) | set(wv or {})
                per_key = {k: {"dump": (dv or {}).get(k), "wxr": (wv or {}).get(k)} for k in keys if (dv or {}).get(k) != (wv or {}).get(k)}
                if per_key:
                    field_mismatches[f].append({"wp_id": wp_id, "diff": per_key})
                continue
            if dv != wv:
                entry = {"wp_id": wp_id, "dump": dv, "wxr": wv}
                if f == "content_html" and isinstance(dv, str) and isinstance(wv, str):
                    entry["dump_len"] = len(dv)
                    entry["wxr_len"] = len(wv)
                field_mismatches[f].append(entry)

    return {
        "dump_count": len(dump),
        "wxr_count": len(wxr),
        "only_in_dump": only_dump,
        "only_in_wxr": only_wxr,
        "both_count": len(both),
        "field_mismatch_counts": {f: len(v) for f, v in field_mismatches.items()},
        "field_mismatches_sample": {f: v[:5] for f, v in field_mismatches.items() if v},
    }


def diff_row_counts(name: str, dump: list[dict], wxr: list[dict]) -> dict[str, Any]:
    return {"file": name, "dump_count": len(dump), "wxr_count": len(wxr), "delta": len(wxr) - len(dump)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump-dir", type=Path, default=Path("jakarta/content/extracted"))
    ap.add_argument("--wxr-dir", type=Path, default=Path("jakarta/content/extracted-wxr"))
    args = ap.parse_args()

    files = ["articles.jsonl", "attachments.jsonl", "terms.jsonl", "users.jsonl", "events.jsonl", "venues.jsonl", "geo.jsonl"]
    data = {}
    for fn in files:
        data[fn] = (load_jsonl(args.dump_dir / fn), load_jsonl(args.wxr_dir / fn))

    report: dict[str, Any] = {"row_counts": [diff_row_counts(fn, d, w) for fn, (d, w) in data.items()]}

    articles_dump, articles_wxr = data["articles.jsonl"]
    report["articles_diff"] = diff_articles(articles_dump, articles_wxr)

    # Category term-name set comparison (WXR has no term_id for these, so
    # compare by (taxonomy, slug) name only).
    dump_terms, wxr_terms = data["terms.jsonl"]
    dump_cat_slugs = {(t["taxonomy"], t["slug"]) for t in dump_terms if t["taxonomy"] == "category"}
    wxr_cat_slugs = {(t["taxonomy"], t["slug"]) for t in wxr_terms if t["taxonomy"] == "category"}
    report["category_term_diff"] = {
        "dump_only": sorted(dump_cat_slugs - wxr_cat_slugs),
        "wxr_only": sorted(wxr_cat_slugs - dump_cat_slugs),
    }

    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
