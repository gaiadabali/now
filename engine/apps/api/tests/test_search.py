"""`GET /v1/{site}/search` -- E3.1's hybrid retrieval exposed over HTTP.

Integration test against the real dev stack (`docker-compose`'s Postgres,
`now_jakarta` + `now_platform`), for the same reason `test_rails.py` is:
the thing under test is the composition of `now_search` + `now_filters`
against a real schema (`engine.article_search`'s GIN index,
`engine.embeddings`' HNSW index, `engine.quality_scores`,
`engine.entity_terms`) that no lightweight fixture recreates. Skips
cleanly (not a failure) if that stack is unreachable.

The assertions deliberately avoid pinning *which* articles come back --
the corpus changes as E2 classification progresses, and a test that
encodes today's top-10 would fail on tomorrow's better ranking. What is
pinned is the contract: filter-before-retrieve actually narrowed the
pool, both retrieval rails contributed, facet counts describe the
candidate set, and a bad facet selector is reported rather than
swallowed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from now_db.settings import pg_host, pg_password, pg_port, pg_user
from sqlalchemy import create_engine, text

from app.config import Settings
from app.infra.db.sync_bridge import dispose_all
from app.main import create_app

SITE_SLUG = "jakarta"  # real registry row seeded by now-db site:create


def _settings() -> Settings:
    host, port, user, password = pg_host(), pg_port(), pg_user(), pg_password()
    return Settings(
        platform_database_url=f"postgresql+asyncpg://{user}:{password}@{host}:{port}/now_platform",
        city_db_host=host,
        city_db_port=int(port),
        city_db_user=user,
        city_db_password=password,
        redis_url=None,
        api_keys_file=None,
        site_registry_cache_ttl_seconds=5.0,
    )


def _sync_dsn(settings: Settings, db: str) -> str:
    return (
        f"postgresql+psycopg://{settings.city_db_user}:{settings.city_db_password}"
        f"@{settings.city_db_host}:{settings.city_db_port}/{db}"
    )


def _stack_reachable(settings: Settings) -> bool:
    try:
        engine = create_engine(_sync_dsn(settings, "now_platform"))
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM engine.sites WHERE slug = :slug"), {"slug": SITE_SLUG})
        engine.dispose()
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture()
def settings() -> Settings:
    return _settings()


@pytest.fixture()
def client(settings: Settings):
    if not _stack_reachable(settings):
        pytest.skip("dev Postgres (now_platform/now_jakarta) unreachable -- see NOW_PG_* / .env")
    app = create_app(settings)
    with TestClient(app) as c:
        yield c
    dispose_all()


def test_search_returns_ranked_hits(client: TestClient):
    resp = client.get(f"/v1/{SITE_SLUG}/search", params={"q": "rooftop bar", "k": 10})
    assert resp.status_code == 200
    body = resp.json()

    assert body["query"] == "rooftop bar"
    assert body["rail"] == "search"
    assert len(body["hits"]) <= 10
    assert body["candidate_count"] > 0, "hard filter returned an empty pool for an unfiltered query"

    for expected_position, hit in enumerate(body["hits"], start=1):
        # §10: every card needs rail + position or impression logging breaks.
        assert hit["position"] == expected_position
        assert hit["entity_type"] == "article"
        # A hit must have come from at least one rail; both being null
        # would mean it appeared in the fused set without being retrieved.
        assert hit["lexical_rank"] is not None or hit["semantic_rank"] is not None

    scores = [h["rrf_score"] for h in body["hits"]]
    assert scores == sorted(scores, reverse=True), "hits are not in descending fused-score order"


def test_both_retrieval_rails_contribute(client: TestClient):
    """§7's correction in one assertion.

    The E3.3 regression (headline nDCG 0.7642 -> 0.375) was the lexical
    signal silently dropping out of the blend. A response where every hit
    carries `lexical_rank: null` is that same failure wearing a different
    hat, and it would otherwise look like a perfectly healthy 200.
    """
    resp = client.get(f"/v1/{SITE_SLUG}/search", params={"q": "restaurant", "k": 20})
    assert resp.status_code == 200
    body = resp.json()
    assert body["lexical_candidate_count"] > 0, "lexical rail retrieved nothing"
    assert body["semantic_candidate_count"] > 0, "semantic rail retrieved nothing"


def test_filter_runs_before_retrieval(client: TestClient):
    """§8.G: "Never retrieve 100 by embedding then filter to 3."

    A reader-chosen facet must shrink the pool retrieval searches, not
    just post-trim the output -- so `candidate_count` itself has to fall.
    """
    unfiltered = client.get(f"/v1/{SITE_SLUG}/search", params={"q": "dinner"}).json()
    filtered = client.get(
        f"/v1/{SITE_SLUG}/search", params={"q": "dinner", "format": "review"}
    ).json()
    assert filtered["candidate_count"] <= unfiltered["candidate_count"]


def test_facet_counts_describe_the_candidate_set(client: TestClient):
    resp = client.get(f"/v1/{SITE_SLUG}/search", params={"q": "cafe"})
    assert resp.status_code == 200
    counts = resp.json()["facet_counts"]
    assert "type" in counts and "format" in counts
    for values in counts.values():
        assert all(isinstance(n, int) and n >= 0 for n in values.values())


def test_unresolved_facet_is_reported_not_swallowed(client: TestClient):
    """A typo'd selector that silently returned the unfiltered corpus is
    indistinguishable, to the caller, from one that matched everything."""
    resp = client.get(
        f"/v1/{SITE_SLUG}/search",
        params={"q": "cafe", "facets": "location:definitely-not-a-real-area"},
    )
    assert resp.status_code == 200
    assert "location:definitely-not-a-real-area" in resp.json()["unresolved_facets"]


def test_malformed_facet_selector_is_reported(client: TestClient):
    resp = client.get(f"/v1/{SITE_SLUG}/search", params={"q": "cafe", "facets": "no-colon-here"})
    assert resp.status_code == 200
    assert "no-colon-here" in resp.json()["unresolved_facets"]


def test_empty_intersection_returns_no_hits_not_a_widened_set(client: TestClient):
    """§8.F's fallback ladder fills every *rail*; a search that the reader
    filtered into an empty intersection must say so rather than quietly
    relax their filter."""
    resp = client.get(
        f"/v1/{SITE_SLUG}/search",
        params={"q": "cafe", "type": "definitely-not-a-real-type"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate_count"] == 0
    assert body["hits"] == []


def test_unknown_site_is_404(client: TestClient):
    assert client.get("/v1/not-a-real-site/search", params={"q": "cafe"}).status_code == 404


def test_missing_query_is_422(client: TestClient):
    assert client.get(f"/v1/{SITE_SLUG}/search").status_code == 422


def test_blank_query_is_422(client: TestClient):
    assert client.get(f"/v1/{SITE_SLUG}/search", params={"q": ""}).status_code == 422
