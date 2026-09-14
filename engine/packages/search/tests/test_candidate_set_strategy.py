"""`engine._retrieve`'s two paths must return the same answer.

A large `candidate_ids` set is applied AFTER retrieval rather than pushed
into the query, because `= ANY(:ids)` with a near-corpus-sized array
defeats both indexes (measured: semantic 1.2ms -> 49.2ms, lexical 15.2ms
-> 49.3ms on the 4,772-article Jakarta corpus). That optimisation is only
legitimate if it is invisible in the results -- these tests are what say
so.

The failure mode being guarded is silent. An approximate unconstrained
fetch returns FEWER rows than asked for, the post-filter path reads that
as "the index is exhausted", and recall quietly drops with a perfectly
healthy-looking 200 response. `test_exact_flag_is_what_makes_overfetch_sound`
pins the specific property (`exact=True` actually reaches `limit`) that
the whole strategy rests on.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from now_search import engine as engine_module
from now_search import query_embedder, semantic
from now_search.engine import SearchEngine

QUERIES = [
    "rooftop bar",
    "nasi goreng",
    "spa wellness",
    "jazz festival",
    "coffee",
    "art gallery",
]


def _published_ids(conn) -> list[int]:
    rows = conn.execute(
        text("SELECT id FROM public.articles WHERE _status = 'published' AND published_at <= now()")
    ).fetchall()
    return [int(r.id) for r in rows]


@pytest.fixture()
def published_ids(conn) -> list[int]:
    ids = _published_ids(conn)
    if len(ids) <= engine_module.LARGE_CANDIDATE_SET:
        pytest.skip(
            "corpus is smaller than LARGE_CANDIDATE_SET -- the post-filter path this "
            "module tests is never taken, so there is nothing to compare"
        )
    return ids


@pytest.mark.parametrize("query", QUERIES)
def test_post_filter_path_matches_constrained_path(conn, published_ids, query, monkeypatch):
    """The optimisation must be invisible: same ids, same order."""
    search_engine = SearchEngine(conn)
    search_engine.warm_up()

    fast = [h.entity_id for h in search_engine.search(query, k=10, candidate_ids=published_ids, compute_facets=False).hits]

    # Raising the threshold above the corpus size forces every rail down
    # the constrained (reference) path, without touching the code itself.
    monkeypatch.setattr(engine_module, "LARGE_CANDIDATE_SET", 10**9)
    reference = [h.entity_id for h in search_engine.search(query, k=10, candidate_ids=published_ids, compute_facets=False).hits]

    assert fast == reference


def test_exact_flag_is_what_makes_overfetch_sound(conn):
    """`exact=True` reaches `limit`; the default HNSW path need not.

    This is the F67 property `_retrieve` depends on. If the default path
    ever started returning full-length results, this test would stop
    proving anything -- so it asserts the *exact* path's completeness
    directly rather than only the gap between the two.
    """
    query_embedder.warm_up()
    vec = query_embedder.embed_query("spa wellness")
    model = query_embedder.model_name()

    available = conn.execute(
        text(
            "SELECT count(*) FROM engine.embeddings WHERE entity_type = 'article' AND model = :m"
        ),
        {"m": model},
    ).scalar_one()
    limit = min(400, int(available))

    exact_hits = semantic.search_semantic(conn, vec, model=model, limit=limit, exact=True)
    assert len(exact_hits) == limit, "exact path must return every row it was asked for"

    ranks = [h.rank for h in exact_hits]
    assert ranks == list(range(1, limit + 1))


def test_renumber_closes_rank_gaps(conn, published_ids):
    """RRF scores by rank, so post-filtered hits must be re-1-indexed or
    the two paths would fuse differently even on identical id sets."""
    search_engine = SearchEngine(conn)
    search_engine.warm_up()
    result = search_engine.search("coffee", k=10, candidate_ids=published_ids, compute_facets=False)

    allowed = set(published_ids)
    for hit in result.hits:
        assert int(hit.entity_id) in allowed, "post-filter let through a row outside the candidate set"
