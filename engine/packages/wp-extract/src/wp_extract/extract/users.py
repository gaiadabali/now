from __future__ import annotations

from typing import Any

import pymysql

from wp_extract.config import TABLE_PREFIX
from wp_extract.db import query
from wp_extract.jsonl import iso

P = TABLE_PREFIX


def extract_users(conn: pymysql.connections.Connection) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # Password hash / activation key deliberately excluded — never extract
    # credential material out of a system being decommissioned.
    users = query(
        conn,
        f"""
        SELECT ID, user_login, user_nicename, user_email, user_url,
               user_registered, display_name
        FROM {P}users
        ORDER BY ID
        """,
    )
    post_counts = query(
        conn,
        f"""
        SELECT post_author, COUNT(*) AS n
        FROM {P}posts
        WHERE post_type = 'post' AND post_status = 'publish'
        GROUP BY post_author
        """,
    )
    counts_by_author = {r["post_author"]: r["n"] for r in post_counts}

    rows = [
        {
            "wp_id": u["ID"],
            "login": u["user_login"],
            "nicename": u["user_nicename"],
            "display_name": u["display_name"],
            "email": u["user_email"],
            "url": u["user_url"] or None,
            "registered": iso(u["user_registered"]),
            "published_post_count": counts_by_author.get(u["ID"], 0),
        }
        for u in users
    ]

    stats = {
        "users_out": len(rows),
        "users_with_published_posts": sum(1 for r in rows if r["published_post_count"] > 0),
    }
    return rows, stats
