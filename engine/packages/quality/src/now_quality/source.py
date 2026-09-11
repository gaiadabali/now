"""One-pass reader for `jakarta/content/extracted/articles.jsonl`, keyed by
the source `wp_id` (== `public.articles.legacy_wp_id`, cast to int). Feeds
both the Yoast-completeness component (Deliverable 1) and the popularity
prior (Deliverable 2) without parsing the 4,772-line file twice.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceMeta:
    views: int | None
    has_focuskw: bool
    has_metadesc: bool
    has_primary_category: bool


def load_source_meta(articles_jsonl: Path) -> dict[int, SourceMeta]:
    out: dict[int, SourceMeta] = {}
    with articles_jsonl.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            wp_id = row.get("wp_id")
            if wp_id is None:
                continue
            meta = row.get("meta") or {}
            views_raw = meta.get("wpb_post_views_count")
            try:
                views = int(views_raw) if views_raw is not None else None
            except (TypeError, ValueError):
                views = None

            def _present(value: object) -> bool:
                return bool(value) and str(value).strip() != ""

            out[int(wp_id)] = SourceMeta(
                views=views,
                has_focuskw=_present(meta.get("_yoast_wpseo_focuskw")),
                has_metadesc=_present(meta.get("_yoast_wpseo_metadesc")),
                has_primary_category=_present(meta.get("_yoast_wpseo_primary_category")),
            )
    return out
