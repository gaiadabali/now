"""Post-F41: `lexical.search_lexical` reads `engine.article_search`
directly -- no cache to build, no warm-up call required before searching.
These tests assume the table has already been populated by
`now-search backfill-tsv` (or the worker) against `now_jakarta`; they skip
cleanly (via the `conn` fixture) if `now_jakarta` is unreachable, and fail
loudly (not skip) if the table exists but is empty, since that would mean
the F41 backfill was never run against this environment."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from now_search import lexical


def _row_count(conn) -> int:
    return conn.execute(text("SELECT count(*) FROM engine.article_search")).scalar_one()


def test_article_search_table_is_populated(conn):
    n = _row_count(conn)
    if n == 0:
        pytest.fail(
            "engine.article_search is empty -- run `now-search backfill-tsv --db now_jakarta` "
            "before running this integration suite"
        )
    assert n > 4000  # 4,772 published articles as of this ticket


def test_search_returns_ranked_hits_best_first(conn):
    hits = lexical.search_lexical(conn, "jakarta", limit=20)
    assert len(hits) > 0
    ranks = [h.rank for h in hits]
    assert ranks == sorted(ranks)
    scores = [h.raw_score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_nonsense_query_returns_no_hits(conn):
    hits = lexical.search_lexical(conn, "zzxxqqnonexistentword12345", limit=10)
    assert hits == []


def test_candidate_id_restriction_is_respected(conn):
    unrestricted = lexical.search_lexical(conn, "jakarta", limit=50)
    assert len(unrestricted) > 5
    allowed = [int(h.entity_id) for h in unrestricted[:3]]
    restricted = lexical.search_lexical(conn, "jakarta", limit=50, candidate_ids=allowed)
    assert {h.entity_id for h in restricted} <= {str(i) for i in allowed}
    assert len(restricted) == 3


def test_no_pg_temp_object_exists(conn):
    """F41 acceptance criterion: the pg_temp cache is deleted, not just
    unused. Asserts directly against pg_catalog that no such relation
    exists in this session -- the strongest test-time proof available
    that the old cache-building code path never runs anymore."""
    row = conn.execute(
        text(
            "SELECT 1 FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relname = 'now_search_lexical_cache' AND n.nspname LIKE 'pg_temp%'"
        )
    ).first()
    assert row is None


def test_f40_listicle_list_block_text_is_indexed(conn):
    """F40's actual bug: a listicle's venue names live in `list` blocks
    (`items` array), which the old SQL approximation never touched. Finds
    a real published article with at least one `list` block, extracts one
    of its item strings, and asserts a lexical search for a distinctive
    word from that item surfaces the article -- proof the real
    `visible_text_out` extractor's list handling made it into
    `engine.article_search.tsv`, not just that the column exists."""
    import re

    rows = conn.execute(
        text(
            """
            SELECT a.id, elem->'items' AS items
              FROM public.articles a
              CROSS JOIN LATERAL jsonb_array_elements(coalesce(a.body_blocks, '[]'::jsonb)) AS elem
             WHERE a._status = 'published' AND elem->>'type' = 'list'
             LIMIT 25
            """
        )
    ).fetchall()
    assert rows, "expected at least one published article with a `list` block"

    found = False
    for article_id, items in rows:
        for item_html in items or []:
            words = [w for w in re.findall(r"[A-Za-z]{5,}", item_html) if w.lower() not in {"strong", "class"}]
            if not words:
                continue
            word = words[0]
            hits = lexical.search_lexical(conn, word, limit=50)
            hit_ids = {int(h.entity_id) for h in hits}
            if article_id in hit_ids:
                found = True
                break
        if found:
            break
    assert found, "no list-block word from any sampled listicle surfaced its own article in lexical search"
