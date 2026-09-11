"""Best-effort display metadata (title/name + slug) for rendered rail
items -- **not** part of the ranking decision, purely so a FE (or this
package's own `cli.py` hand-check) doesn't need a second round trip per
card. Batched, matching Sec.8.G's "per-candidate work runs in memory over
the already-reduced set": one query per entity_type per rail, never one
per item.

`public.articles` has no `slug` column (only `legacy_permalink`, F16/F17 --
verified against the real schema); `public.places` does. Both are surfaced
under one `slug` field on `RailItem` regardless, since a caller rendering a
generic "here's a card" component should not need to know which entity
type spells its identifier differently.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


def fetch_article_titles(conn: Connection, article_ids: list[int]) -> dict[int, tuple[str | None, str | None]]:
    """article_id -> (title, slug). `slug` here is `legacy_permalink`
    (this repo's decision #3: "preserve exactly as found") since Payload's
    `articles` has no first-class `slug` column."""
    if not article_ids:
        return {}
    rows = conn.execute(
        text("SELECT id, title, legacy_permalink FROM public.articles WHERE id = ANY(:ids)"),
        {"ids": article_ids},
    ).fetchall()
    return {r.id: (r.title, r.legacy_permalink) for r in rows}


def fetch_place_names(conn: Connection, place_ids: list[int]) -> dict[int, tuple[str | None, str | None]]:
    """place_id -> (name, slug)."""
    if not place_ids:
        return {}
    rows = conn.execute(
        text("SELECT id, name, slug FROM public.places WHERE id = ANY(:ids)"),
        {"ids": place_ids},
    ).fetchall()
    return {r.id: (r.name, r.slug) for r in rows}
