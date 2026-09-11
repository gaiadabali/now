from __future__ import annotations

from typing import Any

import pymysql

from wp_extract.config import TABLE_PREFIX
from wp_extract.db import query

P = TABLE_PREFIX


def extract_redirects(conn: pymysql.connections.Connection) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items = query(
        conn,
        f"""
        SELECT id, url, match_url, regex, status, group_id, position,
               action_type, action_code, action_data, match_type, title,
               last_count
        FROM {P}redirection_items
        ORDER BY id
        """,
    )

    rows = [
        {
            "wp_id": r["id"],
            "source_url": r["url"],
            "match_url": r["match_url"] or None,
            "is_regex": bool(r["regex"]),
            "match_type": r["match_type"],
            "status": r["status"],
            "action_type": r["action_type"],
            "action_code": r["action_code"],
            "target": r["action_data"] or None,
            "group_id": r["group_id"],
            "title": r["title"] or None,
            "hit_count": r["last_count"],
        }
        for r in items
    ]

    stats = {
        "redirects_out": len(rows),
        "enabled": sum(1 for r in rows if r["status"] == "enabled"),
        "disabled": sum(1 for r in rows if r["status"] == "disabled"),
        "regex_rules": sum(1 for r in rows if r["is_regex"]),
    }
    return rows, stats
