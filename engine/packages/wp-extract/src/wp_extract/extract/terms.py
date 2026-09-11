from __future__ import annotations

from typing import Any

import pymysql

from wp_extract.config import TABLE_PREFIX
from wp_extract.db import query

P = TABLE_PREFIX

# Content taxonomies only. Excluded: nav_menu, ml-slider, wp_theme,
# post_format — WordPress/plugin internal bookkeeping, not editorial
# taxonomy, and no downstream consumer (E1.4) needs them.
CONTENT_TAXONOMIES = ["category", "post_tag", "tribe_events_cat", "event_category", "event-tag"]


def extract_terms(conn: pymysql.connections.Connection) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    placeholders = ",".join(["%s"] * len(CONTENT_TAXONOMIES))
    sql = f"""
        SELECT t.term_id, t.name, t.slug, tt.term_taxonomy_id, tt.taxonomy,
               tt.description, tt.parent, tt.count
        FROM {P}terms t
        JOIN {P}term_taxonomy tt ON tt.term_id = t.term_id
        WHERE tt.taxonomy IN ({placeholders})
        ORDER BY tt.taxonomy, tt.count DESC
    """
    term_rows = query(conn, sql, tuple(CONTENT_TAXONOMIES))

    rows = [
        {
            "term_id": r["term_id"],
            "term_taxonomy_id": r["term_taxonomy_id"],
            "taxonomy": r["taxonomy"],
            "name": r["name"],
            "slug": r["slug"],
            "parent": r["parent"] or None,
            "count": r["count"],
            "description": r["description"] or None,
        }
        for r in term_rows
    ]

    by_taxonomy: dict[str, int] = {}
    for r in rows:
        by_taxonomy[r["taxonomy"]] = by_taxonomy.get(r["taxonomy"], 0) + 1

    stats = {
        "terms_out": len(rows),
        "by_taxonomy": by_taxonomy,
    }
    return rows, stats
