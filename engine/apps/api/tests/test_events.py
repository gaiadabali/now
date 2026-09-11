"""`POST /v1/{site}/events` -- the beacon endpoint (E0.5), updated for
migration 0003 / decision C4 (E0.7) and migration 0007 / F66.

Runs against the same throwaway Postgres container as test_http_api.py
(see engine/apps/api/README.md "Testing") plus
tests/seed/events_schema.sql, which mirrors migrations 0001 + 0002 + 0003 +
0007's `engine.interactions` / `engine.impressions` (including partitions
bracketing "today") into the `now_alpha` / `now_beta` city databases.

Decision C4 (PROGRESS.md): `anon_id`/`session_id` are now genuine UUIDs
(the beacon's `crypto.randomUUID()` change -- see the E0.7 report for the
exact beacon-side diff, not made in this package). `entity_id` is nullable
and, for the two non-entity wire encodings (`search_query` text and an
untagged outbound `url` href), is left NULL server-side while the real
value lands in `query` / `target_url` respectively. `stable_uuid` -- the
old uuid5-hash fallback that made every write succeed regardless of input
-- is deleted; a value that is supposed to be a UUID and isn't now gets a
`400`, never a silent hash and never a `500`.

F66 (PROGRESS.md, migration 0007): `entity_id`, for the rows that *do* name
a real entity, is no longer validated as a uuid -- `public.articles.id`/
`public.places.id`/`public.events.id` are Payload integer serials, so a
real entity_id is a bare non-negative integer string (e.g. `"4821"`),
never a uuid. `anon_id`/`session_id`/`user_id` are untouched by F66 -- they
genuinely are uuids and stay validated as such. A malformed `entity_id`
(non-numeric, or a leftover uuid from a pre-fix client) still gets a
`400`, never a silent pass-through and never a `500`.
"""

from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections.abc import Iterator

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.domain.events.normalize import (
    InvalidEventIdentifierError,
    extract_query,
    extract_target_url,
    interaction_entity_id,
    parse_native_entity_id,
    parse_uuid,
)
from app.main import create_app

from tests.conftest import TEST_DB_HOST, TEST_DB_PASSWORD, TEST_DB_PORT, TEST_DB_USER, make_test_settings


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = make_test_settings()
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def _now_ms() -> int:
    return int(time.time() * 1000)


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _entity_id() -> str:
    """A native-PK-shaped `entity_id` for tests, mirroring the real
    contract post-F66/migration 0007: a bare non-negative integer string,
    exactly what `public.articles.id`/`public.places.id`/`public.events.id`
    (Payload integer serials) produce -- never a uuid. Random rather than
    sequential purely so parallel test runs never collide on the same
    `WHERE entity_id = $1` lookup.
    """
    return str(random.randint(1, 2_000_000_000))


def _fetch(sql: str, *params: object, db: str = "now_alpha") -> list[asyncpg.Record]:
    """Small sync wrapper around asyncpg for direct row assertions -- a
    fresh event loop per call (`asyncio.run`) is fine since these tests are
    plain sync functions using `TestClient`, never themselves inside an
    ambient event loop.
    """

    async def _run() -> list[asyncpg.Record]:
        conn = await asyncpg.connect(
            host=TEST_DB_HOST, port=TEST_DB_PORT, user=TEST_DB_USER, password=TEST_DB_PASSWORD, database=db
        )
        try:
            return await conn.fetch(sql, *params)
        finally:
            await conn.close()

    return asyncio.run(_run())


ALPHA_ORIGIN = "https://alpha.example.test"  # matches tests/seed/sites.sql's `alpha` hostname


# --------------------------------------------------------------------------
# Happy path
# --------------------------------------------------------------------------


def test_happy_path_writes_interactions_and_impressions(client: TestClient) -> None:
    anon = _uuid_str()
    session = _uuid_str()
    entity = _entity_id()  # a real CMS entity id -- a Payload integer PK, as text (F66)
    ts = _now_ms()

    body = {
        "interactions": [
            {
                "anon_id": anon,
                "session_id": session,
                "entity_type": "article",
                "entity_id": entity,
                "kind": "view",
                "surface": "article",
                "ts": ts,
            }
        ],
        "impressions": [
            {
                "session_id": session,
                "anon_id": anon,
                "surface": "article",
                "rail": "complementary",
                "entity_id": entity,
                "position": 1,
                "ts": ts,
            }
        ],
    }

    resp = client.post("/v1/alpha/events", json=body, headers={"Origin": ALPHA_ORIGIN})
    assert resp.status_code == 204
    assert resp.headers["access-control-allow-origin"] == ALPHA_ORIGIN

    rows = _fetch(
        "SELECT anon_id, session_id, entity_id, kind, surface, query, target_url FROM engine.interactions "
        "WHERE entity_id = $1",
        entity,
    )
    assert len(rows) == 1
    assert rows[0]["kind"] == "view"
    # entity_id is `text` as of migration 0007 (F66) -- the native integer
    # PK lands verbatim, not reformatted and not cast to/from a uuid.
    assert rows[0]["entity_id"] == entity
    assert rows[0]["query"] is None
    assert rows[0]["target_url"] is None
    # anon_id/session_id are now genuine uuids end to end (decision C4) --
    # confirm they land exactly as sent, no derivation involved.
    assert rows[0]["anon_id"] == uuid.UUID(anon)
    assert rows[0]["session_id"] == uuid.UUID(session)

    impression_rows = _fetch(
        "SELECT anon_id, rail, position, entity_id FROM engine.impressions WHERE entity_id = $1",
        entity,
    )
    assert len(impression_rows) == 1
    assert impression_rows[0]["rail"] == "complementary"
    assert impression_rows[0]["position"] == 1
    assert impression_rows[0]["entity_id"] == entity


def test_empty_batch_is_accepted_and_writes_nothing(client: TestClient) -> None:
    resp = client.post("/v1/alpha/events", json={"interactions": [], "impressions": []})
    assert resp.status_code == 204


def test_interactions_only_batch(client: TestClient) -> None:
    anon = _uuid_str()
    resp = client.post(
        "/v1/beta/events",
        json={
            "interactions": [
                {
                    "anon_id": anon,
                    "session_id": _uuid_str(),
                    "entity_type": "article",
                    "entity_id": _entity_id(),
                    "kind": "exit",
                    "surface": "article",
                    "dwell_ms": 4200,
                    "scroll_pct": 87.5,
                    "ts": _now_ms(),
                }
            ],
            "impressions": [],
        },
    )
    assert resp.status_code == 204
    rows = _fetch(
        "SELECT dwell_ms, scroll_pct FROM engine.interactions WHERE anon_id = $1",
        uuid.UUID(anon),
        db="now_beta",
    )
    assert len(rows) == 1
    assert rows[0]["dwell_ms"] == 4200
    assert float(rows[0]["scroll_pct"]) == 87.5


# --------------------------------------------------------------------------
# Search normalisation -- decision C1
# --------------------------------------------------------------------------


def test_search_query_lands_in_query_column_not_entity_id(client: TestClient) -> None:
    anon = _uuid_str()
    query_text = "rooftop bar senopati"

    resp = client.post(
        "/v1/alpha/events",
        json={
            "interactions": [
                {
                    "anon_id": anon,
                    "session_id": _uuid_str(),
                    "entity_type": "search_query",
                    "entity_id": query_text,
                    "kind": "search",
                    "surface": "search",
                    "ts": _now_ms(),
                }
            ],
            "impressions": [],
        },
    )
    assert resp.status_code == 204

    rows = _fetch(
        "SELECT entity_type, entity_id, query, kind FROM engine.interactions WHERE anon_id = $1",
        uuid.UUID(anon),
    )
    assert len(rows) == 1
    assert rows[0]["kind"] == "search"
    assert rows[0]["query"] == query_text
    # entity_id is nullable as of migration 0003 -- the raw query text was
    # never cast into it, and there is no synthetic value there either.
    assert rows[0]["entity_id"] is None


def test_extract_query_truncates_to_200_chars() -> None:
    long_query = "a" * 500
    assert extract_query("search_query", long_query) == "a" * 200
    assert extract_query("article", "not a search") is None


# --------------------------------------------------------------------------
# Outbound href -> target_url -- decision C4 (migration 0003)
# --------------------------------------------------------------------------


def test_outbound_event_persists_target_url_and_leaves_entity_id_null(client: TestClient) -> None:
    """The whole point of C4: an untagged outbound click's href must survive
    verbatim for partner click attribution / the ad_events ledger (E4),
    not be destroyed by a hash the way `stable_uuid` used to."""
    anon = _uuid_str()
    href = "https://partner-hotel.example.com/book?ref=now-jakarta&utm_source=now"

    resp = client.post(
        "/v1/alpha/events",
        json={
            "interactions": [
                {
                    "anon_id": anon,
                    "session_id": _uuid_str(),
                    "entity_type": "url",
                    "entity_id": href,
                    "kind": "outbound",
                    "surface": "article",
                    "ts": _now_ms(),
                }
            ],
            "impressions": [],
        },
    )
    assert resp.status_code == 204

    rows = _fetch(
        "SELECT kind, entity_type, entity_id, target_url, query FROM engine.interactions WHERE anon_id = $1",
        uuid.UUID(anon),
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "outbound"
    assert row["target_url"] == href  # the real row: href preserved verbatim
    assert row["entity_id"] is None  # not a hash, not a fabricated value -- NULL
    assert row["query"] is None


def test_extract_target_url_extracts_href_for_url_entity_type() -> None:
    href = "https://example.com/some/partner/link"
    assert extract_target_url("url", href) == href
    assert extract_target_url("article", href) is None


def test_extract_target_url_truncates_defensively() -> None:
    long_href = "https://example.com/" + ("a" * 3000)
    assert len(extract_target_url("url", long_href)) == 2048


def test_interaction_entity_id_none_for_search_and_url_non_entity_types() -> None:
    assert interaction_entity_id("search_query", "rooftop bars") is None
    assert interaction_entity_id("url", "https://example.com") is None


def test_interaction_entity_id_validates_native_integer_pk() -> None:
    """F66/migration 0007: a real entity_id is a bare Payload integer PK
    (e.g. `public.articles.id`), never a uuid -- and it is returned
    verbatim (as `str`, not round-tripped through `int()`), matching F33's
    "store the native PK verbatim" convention exactly."""
    real = "4821"
    assert interaction_entity_id("article", real) == real
    with pytest.raises(InvalidEventIdentifierError):
        interaction_entity_id("article", "not-a-pk")


def test_interaction_entity_id_rejects_a_leftover_uuid() -> None:
    """Before F66 a genuine uuid was exactly what this function required;
    after F66 it must be exactly what it *rejects* -- a uuid is not a
    Payload integer-serial PK. Guards against silently reopening the old
    (wrong) contract."""
    with pytest.raises(InvalidEventIdentifierError):
        interaction_entity_id("article", str(uuid.uuid4()))


def test_parse_native_entity_id_rejects_negative_and_padded_forms() -> None:
    """Stricter than "is this text" on purpose (F66 acceptance bar: still
    reject genuine garbage) -- a negative number and a zero-padded number
    are not shapes a Payload serial ever produces."""
    for bad in ("-1", "007", "4.5", "", " 4821", "4821 "):
        with pytest.raises(InvalidEventIdentifierError):
            parse_native_entity_id(bad, "entity_id")
    assert parse_native_entity_id("0", "entity_id") == "0"
    assert parse_native_entity_id("4821", "entity_id") == "4821"


# --------------------------------------------------------------------------
# UUID validation replaces the old stable_uuid hash -- decision C4
# --------------------------------------------------------------------------


def test_parse_uuid_passes_through_a_real_uuid() -> None:
    real = str(uuid.uuid4())
    assert parse_uuid(real, "anon_id") == uuid.UUID(real)


def test_parse_uuid_rejects_non_uuid_string() -> None:
    with pytest.raises(InvalidEventIdentifierError):
        parse_uuid("not-a-uuid-at-all", "anon_id")


def test_no_stable_uuid_symbol_left_in_normalize_module() -> None:
    """`stable_uuid` must be deleted, not merely unused -- a regression that
    re-adds it (even as dead code) silently reopens the outbound-href data
    loss decision C4 exists to close."""
    import app.domain.events.normalize as normalize_module

    assert not hasattr(normalize_module, "stable_uuid")


def test_non_uuid_anon_id_is_400_not_500(client: TestClient) -> None:
    """The whole point of C4's second half: a malformed identifier is a
    client-payload problem, not a server crash and not a silent hash."""
    resp = client.post(
        "/v1/alpha/events",
        json={
            "interactions": [
                {
                    "anon_id": "not-a-real-uuid",
                    "session_id": _uuid_str(),
                    "entity_type": "article",
                    "entity_id": _entity_id(),
                    "kind": "view",
                    "surface": "article",
                    "ts": _now_ms(),
                }
            ],
            "impressions": [],
        },
    )
    assert resp.status_code == 400


def test_non_uuid_session_id_is_400_not_500(client: TestClient) -> None:
    resp = client.post(
        "/v1/alpha/events",
        json={
            "interactions": [
                {
                    "anon_id": _uuid_str(),
                    "session_id": "also-not-a-uuid",
                    "entity_type": "article",
                    "entity_id": _entity_id(),
                    "kind": "view",
                    "surface": "article",
                    "ts": _now_ms(),
                }
            ],
            "impressions": [],
        },
    )
    assert resp.status_code == 400


def test_invalid_entity_id_for_real_entity_type_is_400_not_500(client: TestClient) -> None:
    """`entity_type='article'` names a real entity -- unlike `search_query`/
    `url`, its `entity_id` must be a native integer PK (F66/migration
    0007), not an arbitrary string."""
    resp = client.post(
        "/v1/alpha/events",
        json={
            "interactions": [
                {
                    "anon_id": _uuid_str(),
                    "session_id": _uuid_str(),
                    "entity_type": "article",
                    "entity_id": "not-a-pk-either",
                    "kind": "view",
                    "surface": "article",
                    "ts": _now_ms(),
                }
            ],
            "impressions": [],
        },
    )
    assert resp.status_code == 400


def test_leftover_uuid_entity_id_for_real_entity_type_is_400_not_500(client: TestClient) -> None:
    """A client still built against the pre-F66 contract (sending a real
    entity as a uuid) must be rejected, not silently accepted -- validation
    changed shape, it did not disappear."""
    resp = client.post(
        "/v1/alpha/events",
        json={
            "interactions": [
                {
                    "anon_id": _uuid_str(),
                    "session_id": _uuid_str(),
                    "entity_type": "article",
                    "entity_id": str(uuid.uuid4()),
                    "kind": "view",
                    "surface": "article",
                    "ts": _now_ms(),
                }
            ],
            "impressions": [],
        },
    )
    assert resp.status_code == 400


def test_invalid_impression_entity_id_is_400_not_500(client: TestClient) -> None:
    resp = client.post(
        "/v1/alpha/events",
        json={
            "interactions": [],
            "impressions": [
                {
                    "session_id": _uuid_str(),
                    "anon_id": _uuid_str(),
                    "surface": "article",
                    "rail": "complementary",
                    "entity_id": "not-a-pk",
                    "position": 1,
                    "ts": _now_ms(),
                }
            ],
        },
    )
    assert resp.status_code == 400


def test_valid_native_pk_impression_entity_id_is_accepted(client: TestClient) -> None:
    """The F66 acceptance bar's other half: a real, valid native PK must no
    longer be rejected the way it was before this fix (impressions'
    entity_id was `uuid NOT NULL` and validated as such)."""
    resp = client.post(
        "/v1/alpha/events",
        json={
            "interactions": [],
            "impressions": [
                {
                    "session_id": _uuid_str(),
                    "anon_id": _uuid_str(),
                    "surface": "article",
                    "rail": "complementary",
                    "entity_id": _entity_id(),
                    "position": 1,
                    "ts": _now_ms(),
                }
            ],
        },
    )
    assert resp.status_code == 204


def test_invalid_identifier_does_not_partially_write_the_batch(client: TestClient) -> None:
    """A bad identifier anywhere in the batch must fail the whole request --
    parameter building (and its validation) happens before any row is
    written, so events before the bad one in the array are never
    persisted."""
    anon = _uuid_str()
    good_entity = _entity_id()
    resp = client.post(
        "/v1/alpha/events",
        json={
            "interactions": [
                {
                    "anon_id": anon,
                    "session_id": _uuid_str(),
                    "entity_type": "article",
                    "entity_id": good_entity,
                    "kind": "view",
                    "surface": "article",
                    "ts": _now_ms(),
                },
                {
                    "anon_id": anon,
                    "session_id": _uuid_str(),
                    "entity_type": "article",
                    "entity_id": "not-a-pk",
                    "kind": "view",
                    "surface": "article",
                    "ts": _now_ms(),
                },
            ],
            "impressions": [],
        },
    )
    assert resp.status_code == 400
    rows = _fetch(
        "SELECT 1 FROM engine.interactions WHERE entity_id = $1",
        good_entity,
    )
    assert rows == []  # the good event never landed either


# --------------------------------------------------------------------------
# Malformed / oversized / unknown-site -> 4xx, never 500
# --------------------------------------------------------------------------


def test_malformed_json_body_is_400_not_500(client: TestClient) -> None:
    resp = client.post(
        "/v1/alpha/events",
        content=b"{not valid json",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400


def test_unknown_kind_is_422(client: TestClient) -> None:
    resp = client.post(
        "/v1/alpha/events",
        json={
            "interactions": [
                {
                    "anon_id": _uuid_str(),
                    "session_id": _uuid_str(),
                    "entity_type": "article",
                    "entity_id": _entity_id(),
                    "kind": "not-a-real-kind",
                    "surface": "article",
                    "ts": _now_ms(),
                }
            ],
            "impressions": [],
        },
    )
    assert resp.status_code == 422


def test_missing_required_field_is_422(client: TestClient) -> None:
    resp = client.post(
        "/v1/alpha/events",
        json={"interactions": [{"anon_id": "a"}], "impressions": []},
    )
    assert resp.status_code == 422


def test_unexpected_field_is_422(client: TestClient) -> None:
    resp = client.post(
        "/v1/alpha/events",
        json={
            "interactions": [
                {
                    "anon_id": _uuid_str(),
                    "session_id": _uuid_str(),
                    "entity_type": "article",
                    "entity_id": _entity_id(),
                    "kind": "view",
                    "surface": "article",
                    "ts": _now_ms(),
                    "unexpected_field": "nope",
                }
            ],
            "impressions": [],
        },
    )
    assert resp.status_code == 422


def test_oversized_batch_is_422(client: TestClient) -> None:
    one = {
        "anon_id": _uuid_str(),
        "session_id": _uuid_str(),
        "entity_type": "article",
        "entity_id": _entity_id(),
        "kind": "view",
        "surface": "article",
        "ts": _now_ms(),
    }
    resp = client.post("/v1/alpha/events", json={"interactions": [one] * 211, "impressions": []})
    assert resp.status_code == 422


def test_oversized_raw_body_is_413(client: TestClient) -> None:
    huge = "x" * (3 * 1024 * 1024)
    resp = client.post(
        "/v1/alpha/events",
        content=huge.encode("utf-8"),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 413


def test_unknown_site_is_404_not_500(client: TestClient) -> None:
    resp = client.post("/v1/does-not-exist/events", json={"interactions": [], "impressions": []})
    assert resp.status_code == 404


def test_ts_outside_partitioned_range_is_400_not_500(client: TestClient) -> None:
    year_2000_ms = 946684800000  # 2000-01-01T00:00:00Z -- well outside the seeded partitions
    resp = client.post(
        "/v1/alpha/events",
        json={
            "interactions": [
                {
                    "anon_id": _uuid_str(),
                    "session_id": _uuid_str(),
                    "entity_type": "article",
                    "entity_id": _entity_id(),
                    "kind": "view",
                    "surface": "article",
                    "ts": year_2000_ms,
                }
            ],
            "impressions": [],
        },
    )
    assert resp.status_code == 400


# --------------------------------------------------------------------------
# CORS allowlist -- decision C2
# --------------------------------------------------------------------------


def test_allowed_origin_gets_cors_header(client: TestClient) -> None:
    resp = client.post(
        "/v1/alpha/events",
        json={"interactions": [], "impressions": []},
        headers={"Origin": ALPHA_ORIGIN},
    )
    assert resp.status_code == 204
    assert resp.headers["access-control-allow-origin"] == ALPHA_ORIGIN


def test_disallowed_origin_is_rejected(client: TestClient) -> None:
    resp = client.post(
        "/v1/alpha/events",
        json={"interactions": [], "impressions": []},
        headers={"Origin": "https://evil.example.com"},
    )
    assert resp.status_code == 403


def test_wrong_sites_origin_is_rejected(client: TestClient) -> None:
    """beta's own origin is not automatically valid for alpha's endpoint."""
    resp = client.post(
        "/v1/alpha/events",
        json={"interactions": [], "impressions": []},
        headers={"Origin": "https://beta.example.test"},
    )
    assert resp.status_code == 403


def test_localhost_origin_allowed_outside_production(client: TestClient) -> None:
    resp = client.post(
        "/v1/alpha/events",
        json={"interactions": [], "impressions": []},
        headers={"Origin": "http://localhost:8933"},
    )
    assert resp.status_code == 204
    assert resp.headers["access-control-allow-origin"] == "http://localhost:8933"


def test_localhost_origin_rejected_in_production() -> None:
    settings = make_test_settings(env="production")
    app = create_app(settings)
    with TestClient(app) as prod_client:
        resp = prod_client.post(
            "/v1/alpha/events",
            json={"interactions": [], "impressions": []},
            headers={"Origin": "http://localhost:8933"},
        )
        assert resp.status_code == 403


def test_no_origin_header_is_not_held_to_cors(client: TestClient) -> None:
    """Server-to-server / curl-style calls send no `Origin` -- CORS is a
    browser enforcement mechanism and doesn't apply to them."""
    resp = client.post("/v1/alpha/events", json={"interactions": [], "impressions": []})
    assert resp.status_code == 204
    assert "access-control-allow-origin" not in resp.headers


def test_preflight_options_allows_configured_origin(client: TestClient) -> None:
    resp = client.options(
        "/v1/alpha/events",
        headers={
            "Origin": ALPHA_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 204
    assert resp.headers["access-control-allow-origin"] == ALPHA_ORIGIN
    assert "POST" in resp.headers["access-control-allow-methods"]


def test_preflight_options_rejects_disallowed_origin(client: TestClient) -> None:
    resp = client.options(
        "/v1/alpha/events",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
    )
    assert resp.status_code == 403


# --------------------------------------------------------------------------
# Rate limiting -- keyed by anon_id (decision C2)
# --------------------------------------------------------------------------


def test_rate_limit_is_keyed_by_anon_id_and_returns_429() -> None:
    settings = make_test_settings(rate_limit_requests=1, rate_limit_window_seconds=60)
    app = create_app(settings)
    anon = _uuid_str()
    body = {
        "interactions": [
            {
                "anon_id": anon,
                "session_id": _uuid_str(),
                "entity_type": "article",
                "entity_id": _entity_id(),
                "kind": "view",
                "surface": "article",
                "ts": _now_ms(),
            }
        ],
        "impressions": [],
    }
    with TestClient(app) as limited_client:
        first = limited_client.post("/v1/alpha/events", json=body)
        second = limited_client.post("/v1/alpha/events", json=body)
        assert first.status_code == 204
        assert second.status_code == 429


def test_rate_limit_does_not_cross_contaminate_different_anon_ids() -> None:
    settings = make_test_settings(rate_limit_requests=1, rate_limit_window_seconds=60)
    app = create_app(settings)

    def _body(anon: str) -> dict[str, object]:
        return {
            "interactions": [
                {
                    "anon_id": anon,
                    "session_id": _uuid_str(),
                    "entity_type": "article",
                    "entity_id": _entity_id(),
                    "kind": "view",
                    "surface": "article",
                    "ts": _now_ms(),
                }
            ],
            "impressions": [],
        }

    with TestClient(app) as limited_client:
        first = limited_client.post("/v1/alpha/events", json=_body(_uuid_str()))
        second = limited_client.post("/v1/alpha/events", json=_body(_uuid_str()))
        assert first.status_code == 204
        assert second.status_code == 204  # different anon_id, independent budget


# --------------------------------------------------------------------------
# Zero site-name literals
# --------------------------------------------------------------------------


def test_no_real_site_literals_in_events_source() -> None:
    """ARCHITECTURE.md §3.5: no hardcoded real-city-name literal may appear
    under engine/. Grepping the files this task owns is a cheap, permanent
    guard against a regression creeping back in.

    CI (`.github/workflows/engine-api-tests.yml`) already greps the whole
    repo for a *quoted* real city slug -- assembled from parts here (never
    spelled out, even in a comment) so this very test doesn't trip that
    repo-wide check on itself.
    """
    import pathlib

    banned = ("".join(["ja", "kar", "ta"]), "".join(["ba", "li"]))
    roots = [
        pathlib.Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "events.py",
        pathlib.Path(__file__).resolve().parents[1] / "app" / "domain" / "events",
    ]
    offenders: list[str] = []
    for root in roots:
        files = [root] if root.is_file() else list(root.rglob("*.py"))
        for f in files:
            text = f.read_text("utf-8").lower()
            for word in banned:
                if word in text:
                    offenders.append(f"{f}: contains '{word}'")
    assert not offenders, "\n".join(offenders)
