"""`GET /v1/{site}/articles/{id}/rails` (E3.8) -- integration test against
the real dev stack (`docker-compose`'s Postgres, `now_jakarta` +
`now_platform`), not a throwaway container: this endpoint's whole point is
composing `now_rails`, which itself only runs against a real schema
(`engine.rail_cache`, `engine.type_relations`, `engine.embeddings`) no
lightweight fixture recreates -- and this dev box has no throwaway
container running today (`tests/test_events.py`'s own suite fails the
same way, for the same reason, independent of this change). Credentials
are never hardcoded here (F47c) -- `now_db.settings` reads the project's
`.env` exactly as every CLI in this repo already does; this test asks
that module for host/port/user/password rather than embedding a value.
Skips cleanly (not a failure) if that stack is unreachable.

Uses `starlette.testclient.TestClient` (sync, runs the ASGI app in its
own thread via a blocking portal) -- the same tool `tests/test_events.py`
already uses, and the one that actually triggers `app.main.create_app`'s
lifespan (`async with AsyncClient(transport=ASGITransport(...))` does
NOT, by itself, run startup/shutdown events -- confirmed the hard way:
`app.state.site_registry` was unset without it).
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from now_db.settings import pg_host, pg_password, pg_port, pg_user
from sqlalchemy import create_engine, text

from app.config import Settings
from app.infra.db.sync_bridge import dispose_all
from app.main import create_app

SITE_SLUG = "jakarta"  # real registry row seeded by now-db site:create -- not a literal this app hardcodes elsewhere


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
    return f"postgresql+psycopg://{settings.city_db_user}:{settings.city_db_password}@{settings.city_db_host}:{settings.city_db_port}/{db}"


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


def _first_real_article_id(settings: Settings) -> int:
    engine = create_engine(_sync_dsn(settings, "now_jakarta"))
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id FROM public.articles ORDER BY id LIMIT 1")).first()
    engine.dispose()
    return row.id


def _clear_rail_cache(settings: Settings, article_id: int) -> None:
    engine = create_engine(_sync_dsn(settings, "now_jakarta"))
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM engine.rail_cache WHERE article_id = :a"), {"a": str(article_id)})
        conn.commit()
    engine.dispose()


def test_rails_returns_all_three_rows(client: TestClient, settings: Settings):
    article_id = _first_real_article_id(settings)
    try:
        resp = client.get(f"/v1/{SITE_SLUG}/articles/{article_id}/rails")
        assert resp.status_code == 200
        body = resp.json()

        assert body["article_id"] == article_id
        assert set(body["rails"].keys()) == {"row1_complementary", "row2_nearby", "row3_similar"}
        for name, rail in body["rails"].items():
            assert rail["rail"] == name
            assert "rung_name" in rail and "rungs_evaluated" in rail
            for item in rail["items"]:
                # Sec.10: every item must carry rail + position for the beacon.
                assert item["rail"] == name
                assert isinstance(item["position"], int) and item["position"] >= 1
    finally:
        _clear_rail_cache(settings, article_id)


def test_rails_unknown_article_is_404(client: TestClient):
    resp = client.get(f"/v1/{SITE_SLUG}/articles/2000000000/rails")
    assert resp.status_code == 404


def test_rails_unknown_site_is_404(client: TestClient):
    resp = client.get("/v1/not-a-real-site/articles/1/rails")
    assert resp.status_code == 404


def test_rails_cache_warm_is_fast(client: TestClient, settings: Settings):
    article_id = _first_real_article_id(settings)
    try:
        first = client.get(f"/v1/{SITE_SLUG}/articles/{article_id}/rails?force_refresh=true")
        assert first.status_code == 200
        assert first.json()["cache"]["hit"] is False

        t0 = time.perf_counter()
        second = client.get(f"/v1/{SITE_SLUG}/articles/{article_id}/rails")
        warm_ms = (time.perf_counter() - t0) * 1000

        assert second.status_code == 200
        assert second.json()["cache"]["hit"] is True
        assert warm_ms < 120, f"warm path p95 target is <120ms, measured {warm_ms:.1f}ms"
    finally:
        _clear_rail_cache(settings, article_id)


def test_rails_synthetic_overlay_is_never_cached(client: TestClient, settings: Settings):
    article_id = _first_real_article_id(settings)
    try:
        resp = client.get(f"/v1/{SITE_SLUG}/articles/{article_id}/rails?synthetic_overlay=true")
        assert resp.status_code == 200
        body = resp.json()
        assert body["synthetic_overlay"] is True
        assert body["cache"]["hit"] is False

        # A real (non-synthetic) request right after must NOT see the
        # synthetic result served back from cache.
        follow_up = client.get(f"/v1/{SITE_SLUG}/articles/{article_id}/rails")
        assert follow_up.json()["synthetic_overlay"] is False
    finally:
        _clear_rail_cache(settings, article_id)
