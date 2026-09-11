"""Real-Postgres integration test against `now_test` (the synthetic tenant
ARCHITECTURE.md §3.5 provisions specifically so cross-cutting engine code
gets exercised against a real, non-city-specific database). `now_test` has
no Payload `public` schema (no CMS instance was ever bound to it), so this
test exercises `engine.embeddings` directly via synthetic rows rather than
`fetch_articles`/`fetch_places` -- the exact functions the real backfill
uses for read/write/kNN, just fed rows we construct instead of rows read
from `public.articles`.

Skips cleanly (not a failure) if `now_test` is unreachable, so this suite
still passes in an environment without the Docker Postgres running -- the
pure-Python tests (`test_offline_provider.py`, `test_textbuild.py`,
`test_worker.py`) are this package's CI-safe baseline; this file is the
"does it actually talk to Postgres correctly" check for local dev.

Uses a `model` value that starts with `test-integration-` and cleans up
every row it writes in a `finally`, so a failed run never leaves debris in
a shared database another task might also be using this wave.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, text

from now_db.settings import city_database_url
from now_embeddings.providers.offline import OfflineProvider
from now_embeddings.store import delete_stale, existing_hashes, knn, upsert_batch

MODEL = f"test-integration-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(city_database_url("now_test"), future=True)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"now_test unreachable: {exc}")
    yield eng
    # Clean up: never leave synthetic test rows behind.
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM engine.embeddings WHERE model = :m"), {"m": MODEL})
    eng.dispose()


def test_upsert_then_read_back_hash(engine):
    provider = OfflineProvider()
    vec = provider.embed_batch(["hello world"])[0]
    with engine.begin() as conn:
        upsert_batch(conn, entity_type="article", model=MODEL, dim=provider.dim, rows=[("1", vec, "hash-a")])

    with engine.connect() as conn:
        hashes = existing_hashes(conn, "article", MODEL)
    assert hashes == {"1": "hash-a"}


def test_upsert_is_idempotent_on_unchanged_hash(engine):
    provider = OfflineProvider()
    vec = provider.embed_batch(["same text"])[0]
    with engine.begin() as conn:
        upsert_batch(conn, entity_type="article", model=MODEL, dim=provider.dim, rows=[("2", vec, "hash-b")])
    with engine.connect() as conn:
        before = existing_hashes(conn, "article", MODEL)["2"]

    # Re-upserting the identical (entity_id, hash) pair must not error and
    # must leave the stored hash exactly as it was -- the real pipeline
    # never even calls upsert in this case (it's filtered out before the
    # model call), but the DB layer itself must tolerate a repeat write.
    with engine.begin() as conn:
        upsert_batch(conn, entity_type="article", model=MODEL, dim=provider.dim, rows=[("2", vec, "hash-b")])
    with engine.connect() as conn:
        after = existing_hashes(conn, "article", MODEL)["2"]
    assert before == after == "hash-b"


def test_knn_returns_nearest_by_cosine_and_excludes_self(engine):
    provider = OfflineProvider()
    rows = [
        ("a", provider.embed_batch(["rooftop bar with cocktails"])[0], "h1"),
        ("b", provider.embed_batch(["rooftop bar with cocktails"])[0], "h2"),  # identical text -> identical vec
        ("c", provider.embed_batch(["budget hostel for backpackers"])[0], "h3"),
    ]
    with engine.begin() as conn:
        upsert_batch(conn, entity_type="place", model=MODEL, dim=provider.dim, rows=rows)

    with engine.connect() as conn:
        neighbors = knn(conn, entity_type="place", model=MODEL, query_vec=rows[0][1], k=5, exclude_entity_id="a")
    ids = [n.entity_id for n in neighbors]
    assert "a" not in ids  # self excluded
    assert ids[0] == "b"  # identical text is the nearest neighbour
    assert neighbors[0].cosine_similarity > 0.999


def test_delete_stale_removes_rows_not_in_keep_set(engine):
    provider = OfflineProvider()
    with engine.begin() as conn:
        upsert_batch(
            conn, entity_type="article", model=MODEL, dim=provider.dim,
            rows=[("keep-1", provider.embed_batch(["x"])[0], "h"), ("drop-1", provider.embed_batch(["y"])[0], "h")],
        )
    with engine.begin() as conn:
        deleted = delete_stale(conn, entity_type="article", model=MODEL, keep_entity_ids={"keep-1", "1", "2"})
    assert deleted >= 1
    with engine.connect() as conn:
        remaining = existing_hashes(conn, "article", MODEL)
    assert "drop-1" not in remaining
    assert "keep-1" in remaining
