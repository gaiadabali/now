"""Real-Postgres tests for `now_search.tsv_store` against `now_jakarta`.
Uses the `write_conn` fixture (open transaction, always rolled back) since
these tests legitimately upsert/delete rows in `engine.article_search` --
this package's own table (migration 0006), not a Payload-owned one -- and
must leave no trace on the shared database afterwards."""

from __future__ import annotations

from sqlalchemy import text

from now_search import tsv_store


def test_fetch_all_for_tsv_uses_real_extractor_on_list_blocks(write_conn):
    """The whole point of F41: body text comes from
    `now_content_clean.metrics.visible_text_out`, which walks `list`
    (and `gallery`/`columns`) blocks -- unlike the old `pg_temp` cache's
    SQL regex approximation, which only pulled `html`/`text`/`caption`
    keys and silently skipped `items` arrays entirely."""
    rows = tsv_store.fetch_all_for_tsv(write_conn)
    assert len(rows) > 4000

    listicle_rows_with_body_text = [
        r for r in rows if r.body_text and len(r.body_text) > 0
    ]
    # Not every article has a list block, but the corpus has plenty of
    # listicles ("7 Best ..."), so body_text should be non-empty for the
    # overwhelming majority of rows -- a near-zero count here would mean
    # visible_text_out silently failed, not that this article type is rare.
    assert len(listicle_rows_with_body_text) > len(rows) * 0.9


def test_upsert_then_search_roundtrip(write_conn):
    rows = tsv_store.fetch_all_for_tsv(write_conn)
    sample = rows[:5]
    tsv_store.upsert_tsv_batch(write_conn, sample)

    hashes = tsv_store.existing_hashes(write_conn)
    for r in sample:
        assert hashes[r.article_id] == r.text_hash


def test_existing_hash_for_single_row(write_conn):
    rows = tsv_store.fetch_all_for_tsv(write_conn)
    one = rows[0]
    tsv_store.upsert_tsv_batch(write_conn, [one])
    assert tsv_store.existing_hash_for(write_conn, one.article_id) == one.text_hash
    assert tsv_store.existing_hash_for(write_conn, -999999) is None


def test_upsert_is_idempotent_on_unchanged_hash(write_conn):
    rows = tsv_store.fetch_all_for_tsv(write_conn)
    one = rows[0]
    tsv_store.upsert_tsv_batch(write_conn, [one])
    first_hash = tsv_store.existing_hash_for(write_conn, one.article_id)
    tsv_store.upsert_tsv_batch(write_conn, [one])
    second_hash = tsv_store.existing_hash_for(write_conn, one.article_id)
    assert first_hash == second_hash == one.text_hash


def test_fetch_one_for_tsv_matches_fetch_all(write_conn):
    rows = tsv_store.fetch_all_for_tsv(write_conn)
    target = rows[10]
    single = tsv_store.fetch_one_for_tsv(write_conn, target.article_id)
    assert single is not None
    assert single.text_hash == target.text_hash
    assert single.body_text == target.body_text


def test_fetch_one_for_tsv_returns_none_for_missing_article(write_conn):
    assert tsv_store.fetch_one_for_tsv(write_conn, -999999) is None


def test_delete_stale_removes_only_non_kept_rows(write_conn):
    """Scoped deliberately to a controlled 3-row slice: `delete_stale`'s
    real SQL is `entity_id <> ALL(:keep)` with no other WHERE clause, so
    exercising it against the full ~4,772-row backfilled table (even
    inside a rolled-back transaction) would wipe the whole table for the
    duration of this test for no added signal. Wiping and reseeding just
    these 3 rows keeps the assertion about *which* rows survive precise
    without touching -- even transiently -- the rest of the table."""
    rows = tsv_store.fetch_all_for_tsv(write_conn)[:3]
    write_conn.execute(text("DELETE FROM engine.article_search"))
    tsv_store.upsert_tsv_batch(write_conn, rows)
    keep_ids = {rows[0].article_id}
    deleted = tsv_store.delete_stale(write_conn, keep_ids)
    assert deleted == 2
    remaining = tsv_store.existing_hashes(write_conn)
    assert remaining == {rows[0].article_id: rows[0].text_hash}
