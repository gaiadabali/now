"""Recomputes `engine.hidden_rival_flags` (migration 0009) -- the offline
half of `now_filters.hidden_rival`. ARCHITECTURE.md principle 2: `engine`
is derived from `public` and rebuildable at any time; this module is that
rebuild for the hidden-rival signal specifically.

Two independent detectors, matching that module's two documented signals:

  featured_mention   role='featured' place_mentions row whose place NAME
                      matches a type's subtype lexicon (every L1 type).
  title              a candidate's own article TITLE matches a type's
                      lexicon, for `title_signal_enabled_types()` only
                      (currently `stay`), and only for candidates whose
                      own declared `primary_type` is non-venue
                      (`exclude_same=false`) or NULL -- a venue-typed
                      candidate is untouched by this signal (unchanged
                      from the first pass).

A full TRUNCATE + re-INSERT per run: the table is small (low hundreds of
rows per city, measured), so a full recompute is simpler than an
incremental diff and can never leave a stale partial state between runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_filters.hidden_rival import build_name_pattern, default_lexicon, title_signal_enabled_types
from now_filters.type_relations import TypeRelation, load_type_relations

_FEATURED_MENTIONS_SQL = text(
    """
    SELECT pm.article_id, pl.name
      FROM public.place_mentions pm
      JOIN public.places pl ON pl.id = pm.place_id
     WHERE pm.role = 'featured'
    """
)

_ARTICLE_TITLES_SQL = text(
    """
    SELECT id, title, primary_type::text AS primary_type
      FROM public.articles
     WHERE _status = 'published'
    """
)

_TRUNCATE_SQL = text("TRUNCATE engine.hidden_rival_flags")

_INSERT_SQL = text(
    """
    INSERT INTO engine.hidden_rival_flags (article_id, matched_type, signal)
    VALUES (:article_id, :matched_type, :signal)
    ON CONFLICT (article_id, matched_type, signal) DO NOTHING
    """
)


def _compiled_patterns(types: list[str], lexicon: dict[str, tuple[str, ...]]) -> dict[str, re.Pattern[str]]:
    """One compiled Python regex per type, `\\y` swapped for `\\b` (see
    `hidden_rival.py`'s own note on the Postgres-vs-Python dialect
    difference) -- this module runs the match in Python, over rows pulled
    once, rather than issuing one Postgres `~*` per row per type."""
    out: dict[str, re.Pattern[str]] = {}
    for t in types:
        pattern = build_name_pattern({t}, lexicon)
        if pattern is not None:
            out[t] = re.compile(pattern.replace(r"\y", r"\b"), re.IGNORECASE)
    return out


@dataclass(frozen=True)
class RecomputeReport:
    featured_mention_rows: int
    title_rows: int
    total_rows: int


def recompute_hidden_rival_flags(conn: Connection) -> RecomputeReport:
    lexicon = default_lexicon()
    all_types = sorted(lexicon.keys())
    patterns = _compiled_patterns(all_types, lexicon)

    to_insert: list[dict[str, str]] = []

    # --- featured_mention -------------------------------------------------
    featured_count = 0
    for article_id, name in conn.execute(_FEATURED_MENTIONS_SQL).fetchall():
        if not name:
            continue
        for type_slug, pattern in patterns.items():
            if pattern.search(name):
                to_insert.append({"article_id": str(article_id), "matched_type": type_slug, "signal": "featured_mention"})
                featured_count += 1

    # --- title --------------------------------------------------------------
    relations: dict[str, TypeRelation] = load_type_relations(conn)
    non_venue_types = {t for t, r in relations.items() if not r.exclude_same}
    enabled = title_signal_enabled_types()
    title_count = 0
    if enabled:
        title_patterns = {t: patterns[t] for t in enabled if t in patterns}
        for article_id, title, primary_type in conn.execute(_ARTICLE_TITLES_SQL).fetchall():
            if not title:
                continue
            # Venue-typed candidates are untouched by this signal (module
            # docstring's own constraint, carried from the review): only
            # non-venue-typed or unclassified candidates are checked.
            if primary_type is not None and primary_type not in non_venue_types:
                continue
            for type_slug, pattern in title_patterns.items():
                if pattern.search(title):
                    to_insert.append({"article_id": str(article_id), "matched_type": type_slug, "signal": "title"})
                    title_count += 1

    conn.execute(_TRUNCATE_SQL)
    if to_insert:
        conn.execute(_INSERT_SQL, to_insert)

    return RecomputeReport(
        featured_mention_rows=featured_count,
        title_rows=title_count,
        total_rows=len(to_insert),
    )
