from __future__ import annotations

from collections import defaultdict
from typing import Any

import pymysql

from wp_extract.config import TABLE_PREFIX
from wp_extract.db import query

P = TABLE_PREFIX


def fetch_posts(conn: pymysql.connections.Connection, post_type: str, status: str | None = "publish") -> list[dict[str, Any]]:
    if status is None:
        sql = f"SELECT * FROM {P}posts WHERE post_type=%s ORDER BY ID"
        return query(conn, sql, (post_type,))
    sql = f"SELECT * FROM {P}posts WHERE post_type=%s AND post_status=%s ORDER BY ID"
    return query(conn, sql, (post_type, status))


def fetch_term_names_by_object(conn: pymysql.connections.Connection, taxonomy: str) -> dict[int, list[str]]:
    """object_id -> [term names] for a given taxonomy, across ALL post types.
    Callers filter down to the object_ids they care about.
    """
    sql = f"""
        SELECT tr.object_id AS object_id, t.name AS name, t.term_id AS term_id
        FROM {P}term_relationships tr
        JOIN {P}term_taxonomy tt ON tt.term_taxonomy_id = tr.term_taxonomy_id
        JOIN {P}terms t ON t.term_id = tt.term_id
        WHERE tt.taxonomy = %s
        ORDER BY tr.object_id, t.name
    """
    rows = query(conn, sql, (taxonomy,))
    out: dict[int, list[str]] = defaultdict(list)
    for r in rows:
        out[r["object_id"]].append(r["name"])
    return out


def fetch_term_ids_by_object(conn: pymysql.connections.Connection, taxonomy: str) -> dict[int, list[int]]:
    sql = f"""
        SELECT tr.object_id AS object_id, t.term_id AS term_id
        FROM {P}term_relationships tr
        JOIN {P}term_taxonomy tt ON tt.term_taxonomy_id = tr.term_taxonomy_id
        JOIN {P}terms t ON t.term_id = tt.term_id
        WHERE tt.taxonomy = %s
        ORDER BY tr.object_id
    """
    rows = query(conn, sql, (taxonomy,))
    out: dict[int, list[int]] = defaultdict(list)
    for r in rows:
        out[r["object_id"]].append(r["term_id"])
    return out


def fetch_postmeta(conn: pymysql.connections.Connection, meta_keys: list[str]) -> dict[int, dict[str, str]]:
    """post_id -> {meta_key: meta_value} restricted to the given keys, across
    ALL post types. Callers filter down to the post_ids they care about.
    """
    placeholders = ",".join(["%s"] * len(meta_keys))
    sql = f"""
        SELECT post_id, meta_key, meta_value
        FROM {P}postmeta
        WHERE meta_key IN ({placeholders})
    """
    rows = query(conn, sql, tuple(meta_keys))
    out: dict[int, dict[str, str]] = defaultdict(dict)
    for r in rows:
        out[r["post_id"]][r["meta_key"]] = r["meta_value"]
    return out


def permalink_for(site_home: str, post_name: str) -> str:
    return f"{site_home}/{post_name}/"
