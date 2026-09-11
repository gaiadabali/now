from __future__ import annotations

from typing import Any

import pymysql

from wp_extract.config import Config
from wp_extract.extract.common import (
    fetch_postmeta,
    fetch_term_names_by_object,
    fetch_term_ids_by_object,
    permalink_for,
)
from wp_extract.extract.common import fetch_posts
from wp_extract.jsonl import iso

# Curated per ARCHITECTURE.md §6 "Key meta" — tags are intentionally excluded
# from the article record's meta (1,347 terms, 1,071 unused, discarded) and
# always emitted as an empty list per the frozen contract example.
ARTICLE_META_KEYS = [
    "_yoast_wpseo_focuskw",
    "_yoast_wpseo_metadesc",
    "_yoast_wpseo_primary_category",
    "wpb_post_views_count",
    "_thumbnail_id",
]


def extract_articles(conn: pymysql.connections.Connection, cfg: Config) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    posts = fetch_posts(conn, "post", "publish")
    post_ids = {p["ID"] for p in posts}

    categories_by_post = fetch_term_names_by_object(conn, "category")
    category_ids_by_post = fetch_term_ids_by_object(conn, "category")
    meta_by_post = fetch_postmeta(conn, ARTICLE_META_KEYS)

    with_categories = 0
    rows: list[dict[str, Any]] = []
    for p in posts:
        pid = p["ID"]
        cats = categories_by_post.get(pid, [])
        if cats:
            with_categories += 1
        meta = meta_by_post.get(pid, {})
        thumb = meta.get("_thumbnail_id")
        meta_out = {k: v for k, v in meta.items() if k != "_thumbnail_id"}

        # Primary category (Yoast) first in the list, if it resolves to one
        # of this post's assigned categories.
        primary_cat_id = meta.get("_yoast_wpseo_primary_category")
        if primary_cat_id and cats:
            ids = category_ids_by_post.get(pid, [])
            names = categories_by_post.get(pid, [])
            try:
                idx = ids.index(int(primary_cat_id))
                if idx != 0:
                    cats = [names[idx]] + names[:idx] + names[idx + 1 :]
            except (ValueError, IndexError):
                pass

        rows.append(
            {
                "wp_id": pid,
                "type": "post",
                "status": p["post_status"],
                "title": p["post_title"],
                "slug": p["post_name"],
                "content_html": p["post_content"],
                "excerpt": p["post_excerpt"],
                "date": iso(p["post_date"]),
                "modified": iso(p["post_modified"]),
                "author_id": p["post_author"],
                "permalink": permalink_for(cfg.site_home, p["post_name"]),
                "categories": cats,
                "tags": [],  # discarded per ARCHITECTURE.md §6 — 1,071/1,347 unused
                "meta": meta_out,
                "thumbnail_id": int(thumb) if thumb not in (None, "") else None,
            }
        )

    stats = {
        "posts_in": len(posts),
        "posts_out": len(rows),
        "with_categories": with_categories,
        "coverage_pct": round(100 * with_categories / len(rows), 1) if rows else 0.0,
    }
    return rows, stats
