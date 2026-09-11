from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

from wxr_extract.extract import (
    build_articles,
    build_attachments,
    build_events_and_venues,
    build_geo,
    build_terms,
    build_users,
    dedupe_items,
)
from wxr_extract.jsonl import write_jsonl
from wxr_extract.wxr_parser import read_channel_meta, iter_items


class _PeakRssSampler:
    """Samples this process's RSS in a background thread via psutil, so we
    can report real peak memory for the streaming parse rather than assert
    it. Falls back to reporting "psutil unavailable" rather than fabricating
    a number if psutil can't be imported.
    """

    def __init__(self, interval_s: float = 0.05) -> None:
        self.interval_s = interval_s
        self.peak_bytes = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._available = False
        try:
            import psutil  # noqa: F401

            self._available = True
        except ImportError:
            pass

    def __enter__(self) -> "_PeakRssSampler":
        if self._available:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def _run(self) -> None:
        import psutil

        proc = psutil.Process()
        while not self._stop.is_set():
            try:
                rss = proc.memory_info().rss
                if rss > self.peak_bytes:
                    self.peak_bytes = rss
            except Exception:
                pass
            time.sleep(self.interval_s)

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def report(self) -> str:
        if not self._available:
            return "psutil not installed — peak RSS not measured"
        return f"{self.peak_bytes / (1024 * 1024):.1f} MB (sampled every {self.interval_s * 1000:.0f}ms via psutil.Process().memory_info().rss)"


def run_extraction(input_paths: list[Path], output_dir: Path, site_home: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    all_authors: dict[str, dict[str, Any]] = {}
    all_terms: list[dict[str, Any]] = []
    items_by_source: list[list] = []

    with _PeakRssSampler() as sampler:
        for path in input_paths:
            meta = read_channel_meta(path)
            all_authors.update(meta.authors_by_login)
            all_terms.extend(meta.terms)

            items = list(iter_items(path))
            items_by_source.append(items)

        items, dupe_count = dedupe_items(items_by_source)
        peak_rss_report = sampler.report()

    articles, articles_stats = build_articles(items, all_authors, site_home)
    attachments, attachments_stats = build_attachments(items, site_home)
    terms, terms_stats = build_terms(items, all_terms)
    users, users_stats = build_users(all_authors, articles)
    geo, geo_stats = build_geo(items)
    events, events_stats, venues, venues_stats = build_events_and_venues(items)

    write_jsonl(output_dir / "articles.jsonl", articles)
    write_jsonl(output_dir / "attachments.jsonl", attachments)
    write_jsonl(output_dir / "terms.jsonl", terms)
    write_jsonl(output_dir / "users.jsonl", users)
    write_jsonl(output_dir / "geo.jsonl", geo)
    write_jsonl(output_dir / "events.jsonl", events)
    write_jsonl(output_dir / "venues.jsonl", venues)

    post_type_counts: dict[str, int] = {}
    status_by_type: dict[str, dict[str, int]] = {}
    for it in items:
        post_type_counts[it.post_type] = post_type_counts.get(it.post_type, 0) + 1
        status_by_type.setdefault(it.post_type, {})
        status_by_type[it.post_type][it.status or "?"] = status_by_type[it.post_type].get(it.status or "?", 0) + 1

    manifest = {
        "inputs": [str(p) for p in input_paths],
        "site_home": site_home,
        "items_total_after_dedupe": len(items),
        "duplicate_items_dropped": dupe_count,
        "post_type_counts": post_type_counts,
        "status_by_post_type": status_by_type,
        "peak_rss": peak_rss_report,
        "stats": {
            "articles": articles_stats,
            "attachments": attachments_stats,
            "terms": terms_stats,
            "users": users_stats,
            "geo": geo_stats,
            "events": events_stats,
            "venues": venues_stats,
        },
    }
    (output_dir / "extraction_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wxr-extract", description="Stream WXR exports into wp-extract's frozen JSONL contract.")
    parser.add_argument("--input", nargs="+", required=True, type=Path, help="One or more WXR .xml files (merged, deduped by wp_id)")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--site-home", required=True, help="e.g. https://www.nowbali.co.id (no trailing slash)")
    args = parser.parse_args(argv)

    for p in args.input:
        if not p.is_file():
            print(f"error: input file not found: {p}", file=sys.stderr)
            return 2

    manifest = run_extraction(args.input, args.output_dir, args.site_home.rstrip("/"))
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
