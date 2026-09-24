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

## Freshness (third pass, 2026-09-24)

A precomputed table goes stale the moment new content is published, which
is exactly the failure mode the second pass's speed fix traded into: a
fresh "Hard Rock Hotel Bali presents..." event is not flagged until
something recomputes it. Three mechanisms close that gap, in decreasing
order of how fast they react and increasing order of how much they can
catch:

  1. `recompute_flags_for_article` -- ONE article, called from
     `engine/apps/worker/app/consumer.py`'s domain-event handler on
     `article.published`/`article.republished` (recompute) and
     `article.unpublished` (`remove_flags_for_article` -- delete only).
     This is the fast path: a publish is flagged within the same
     at-least-once delivery the re-embed worker already uses, not
     tomorrow's cron.
  2. **No event exists for "place_mentions changed independent of the
     article being republished."** `now_place_extraction` is an offline
     CLI batch pipeline (`now-place-extract run --city <city>`), not
     triggered by any per-article domain event -- searched the CMS hooks
     and this package's own dependents before writing this, there is
     nothing to hook. A place-extraction run that changes an article's
     mentions without also touching the article row itself (no
     `article.published`/`.republished` event fires) is caught by (3),
     not (1) -- stated plainly rather than silently assumed away.
  3. `recompute_hidden_rival_flags` (this module's full recompute,
     unchanged in shape from the second pass) as a nightly safety net
     (`app/jobs.py`'s cron), now DIFF-AWARE: it reports how many
     (article_id, matched_type, signal) rows were added/removed relative
     to what was already there, not just a blind total. A non-zero
     added/removed count on a night nothing else changed is the signal
     that (1) or (2) missed something -- logged, not raised, since this
     job's own job IS to catch and correct exactly that drift.

Every write is idempotent: `recompute_flags_for_article` diffs against
what is already there for that one article and only touches the rows that
differ; `remove_flags_for_article` is a plain, repeatable DELETE.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_filters.hidden_rival import build_name_pattern, default_lexicon, title_signal_enabled_types
from now_filters.type_relations import TypeRelation, load_type_relations

DEFAULT_ARTICLES_TABLE = "public.articles"
DEFAULT_PLACE_MENTIONS_TABLE = "public.place_mentions"
DEFAULT_PLACES_TABLE = "public.places"
DEFAULT_FLAGS_TABLE = "engine.hidden_rival_flags"

_INSERT_SQL_TEMPLATE = """
    INSERT INTO {flags_table} (article_id, matched_type, signal)
    VALUES (:article_id, :matched_type, :signal)
    ON CONFLICT (article_id, matched_type, signal) DO NOTHING
"""

_DELETE_ROW_SQL_TEMPLATE = """
    DELETE FROM {flags_table}
     WHERE article_id = :article_id AND matched_type = :matched_type AND signal = :signal
"""


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


def _title_non_venue_types(relations: dict[str, TypeRelation]) -> set[str]:
    return {t for t, r in relations.items() if not r.exclude_same}


def _featured_mention_matches(
    conn: Connection, patterns: dict[str, re.Pattern[str]], *, article_id: str | None, place_mentions_table: str, places_table: str
) -> set[tuple[str, str]]:
    """(article_id, matched_type) pairs from `role='featured'` mentions --
    every L1 type, unrestricted by the candidate's own declared type (see
    `hidden_rival.py` module docstring for why: this signal is independent
    of what the classifier already decided). `article_id=None` scans every
    article (the full recompute); a real id scopes to just that one."""
    sql = f"""
        SELECT pm.article_id, pl.name
          FROM {place_mentions_table} pm
          JOIN {places_table} pl ON pl.id = pm.place_id
         WHERE pm.role = 'featured'
           {"AND pm.article_id = :article_id" if article_id is not None else ""}
    """
    params = {"article_id": int(article_id)} if article_id is not None else {}
    out: set[tuple[str, str]] = set()
    for row_article_id, name in conn.execute(text(sql), params).fetchall():
        if not name:
            continue
        for type_slug, pattern in patterns.items():
            if pattern.search(name):
                out.add((str(row_article_id), type_slug))
    return out


def _title_matches(
    conn: Connection,
    patterns: dict[str, re.Pattern[str]],
    relations: dict[str, TypeRelation],
    *,
    article_id: str | None,
    articles_table: str,
) -> set[tuple[str, str]]:
    """(article_id, matched_type) pairs from the TITLE signal --
    `title_signal_enabled_types()` only, and only for candidates whose own
    `primary_type` is non-venue or NULL (module docstring's constraint,
    unchanged from the second pass)."""
    enabled = title_signal_enabled_types()
    if not enabled:
        return set()
    title_patterns = {t: patterns[t] for t in enabled if t in patterns}
    if not title_patterns:
        return set()

    non_venue_types = _title_non_venue_types(relations)
    sql = f"""
        SELECT id, title, primary_type::text AS primary_type
          FROM {articles_table}
         WHERE _status = 'published'
           {"AND id = :article_id" if article_id is not None else ""}
    """
    params = {"article_id": int(article_id)} if article_id is not None else {}
    out: set[tuple[str, str]] = set()
    for row_id, title, primary_type in conn.execute(text(sql), params).fetchall():
        if not title:
            continue
        if primary_type is not None and primary_type not in non_venue_types:
            continue
        for type_slug, pattern in title_patterns.items():
            if pattern.search(title):
                out.add((str(row_id), type_slug))
    return out


def _existing_flags(conn: Connection, *, article_id: str | None, flags_table: str) -> set[tuple[str, str, str]]:
    sql = f"SELECT article_id, matched_type, signal FROM {flags_table}"
    params = {}
    if article_id is not None:
        sql += " WHERE article_id = :article_id"
        params["article_id"] = str(article_id)
    return {(row.article_id, row.matched_type, row.signal) for row in conn.execute(text(sql), params).fetchall()}


def _apply_diff(conn: Connection, *, added: set[tuple[str, str, str]], removed: set[tuple[str, str, str]], flags_table: str) -> None:
    insert_sql = text(_INSERT_SQL_TEMPLATE.format(flags_table=flags_table))
    delete_sql = text(_DELETE_ROW_SQL_TEMPLATE.format(flags_table=flags_table))
    for article_id, matched_type, signal in removed:
        conn.execute(delete_sql, {"article_id": article_id, "matched_type": matched_type, "signal": signal})
    for article_id, matched_type, signal in added:
        conn.execute(insert_sql, {"article_id": article_id, "matched_type": matched_type, "signal": signal})


# ---------------------------------------------------------------------------
# Full recompute -- the nightly safety net (item 3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecomputeReport:
    featured_mention_rows: int
    title_rows: int
    total_rows: int
    added: int
    removed: int
    unchanged: int

    @property
    def changed(self) -> bool:
        """A non-zero added/removed count on a run where the per-article
        event path (and, for now, the undetected place-mentions gap) is
        working correctly should be rare -- this is the signal the
        docstring's item 3 describes: "a non-zero change count is a
        signal the event path missed something." """
        return self.added > 0 or self.removed > 0


def recompute_hidden_rival_flags(
    conn: Connection,
    *,
    articles_table: str = DEFAULT_ARTICLES_TABLE,
    place_mentions_table: str = DEFAULT_PLACE_MENTIONS_TABLE,
    places_table: str = DEFAULT_PLACES_TABLE,
    flags_table: str = DEFAULT_FLAGS_TABLE,
) -> RecomputeReport:
    """Recomputes every row, diffed against what is already there (third
    pass: was a blind TRUNCATE + re-INSERT, which could never report
    whether anything had actually changed). The table is small (low
    hundreds of rows per city, measured), so computing the full new set in
    Python and diffing it against the full existing set is simpler than an
    incremental per-row comparison and cannot leave a stale partial state
    between runs -- same reasoning the original docstring gave, preserved
    here for the "why not incremental" question."""
    lexicon = default_lexicon()
    all_types = sorted(lexicon.keys())
    patterns = _compiled_patterns(all_types, lexicon)
    relations = load_type_relations(conn)

    featured = _featured_mention_matches(
        conn, patterns, article_id=None, place_mentions_table=place_mentions_table, places_table=places_table
    )
    titles = _title_matches(conn, patterns, relations, article_id=None, articles_table=articles_table)

    new_rows = {(a, t, "featured_mention") for a, t in featured} | {(a, t, "title") for a, t in titles}
    existing_rows = _existing_flags(conn, article_id=None, flags_table=flags_table)

    added = new_rows - existing_rows
    removed = existing_rows - new_rows
    unchanged = new_rows & existing_rows

    _apply_diff(conn, added=added, removed=removed, flags_table=flags_table)

    return RecomputeReport(
        featured_mention_rows=len(featured),
        title_rows=len(titles),
        total_rows=len(new_rows),
        added=len(added),
        removed=len(removed),
        unchanged=len(unchanged),
    )


# ---------------------------------------------------------------------------
# Per-article recompute -- the fast path (item 1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArticleRecomputeReport:
    added: int
    removed: int
    unchanged: int

    @property
    def changed(self) -> bool:
        return self.added > 0 or self.removed > 0


def recompute_flags_for_article(
    conn: Connection,
    article_id: str | int,
    *,
    articles_table: str = DEFAULT_ARTICLES_TABLE,
    place_mentions_table: str = DEFAULT_PLACE_MENTIONS_TABLE,
    places_table: str = DEFAULT_PLACES_TABLE,
    flags_table: str = DEFAULT_FLAGS_TABLE,
) -> ArticleRecomputeReport:
    """Recomputes hidden-rival flags for exactly ONE article -- called from
    `engine/apps/worker/app/consumer.py` on `article.published`/
    `.republished`. Idempotent: diffs this article's new flag set against
    what is already there and only touches the difference, so redelivery
    of the same domain event (this stream's own at-least-once contract,
    per `now_embeddings.worker`'s docstring) is always a safe no-op on the
    second attempt.

    Scans the SAME two signals as the full recompute, restricted to this
    one `article_id` -- not a separate, narrower implementation that could
    disagree with the nightly safety net about what "this article's flags"
    means.
    """
    article_id = str(article_id)
    lexicon = default_lexicon()
    all_types = sorted(lexicon.keys())
    patterns = _compiled_patterns(all_types, lexicon)
    relations = load_type_relations(conn)

    featured = _featured_mention_matches(
        conn, patterns, article_id=article_id, place_mentions_table=place_mentions_table, places_table=places_table
    )
    titles = _title_matches(conn, patterns, relations, article_id=article_id, articles_table=articles_table)

    new_rows = {(a, t, "featured_mention") for a, t in featured} | {(a, t, "title") for a, t in titles}
    existing_rows = _existing_flags(conn, article_id=article_id, flags_table=flags_table)

    added = new_rows - existing_rows
    removed = existing_rows - new_rows
    unchanged = new_rows & existing_rows

    _apply_diff(conn, added=added, removed=removed, flags_table=flags_table)

    return ArticleRecomputeReport(added=len(added), removed=len(removed), unchanged=len(unchanged))


def remove_flags_for_article(
    conn: Connection,
    article_id: str | int,
    *,
    flags_table: str = DEFAULT_FLAGS_TABLE,
) -> int:
    """Called on `article.unpublished` (and would serve a hard delete
    equally well, if one is ever emitted). An unpublished article is
    excluded from every rail query by its own `_status`/`published_at`
    predicate regardless of what this table says about it, so this is not
    load-bearing for correctness today -- it is done anyway because a
    flags table that still names articles nobody can be shown is not an
    honest mirror of `public` (principle 2), and because a republish of a
    once-unpublished article should not see the recompute silently
    no-op against leftover rows from a different published version of the
    title."""
    article_id = str(article_id)
    result = conn.execute(
        text(f"DELETE FROM {flags_table} WHERE article_id = :article_id"), {"article_id": article_id}
    )
    return result.rowcount or 0
