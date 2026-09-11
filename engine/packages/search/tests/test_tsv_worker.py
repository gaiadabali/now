"""Unit tests for the routing/filtering logic in
`TsvRefreshWorker.handle_payload` -- no real Redis or Postgres, mirroring
`now_embeddings/tests/test_worker.py`'s approach exactly.
`TsvRefreshWorker.__init__` opens a real Redis connection (`ensure_group`)
and a real platform DB engine, so tests build the instance via
`object.__new__` and set only the attributes `handle_payload` actually
reads, then monkeypatch the module-level `get_site`/`fetch_one`/
`refresh_row`/`city_engine` names it calls."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import now_search.tsv_worker as worker_mod
from now_search.tsv_worker import REFRESH_EVENTS, TsvRefreshWorker


def _bare_worker() -> TsvRefreshWorker:
    w = object.__new__(TsvRefreshWorker)
    w._platform_engine = mock.MagicMock()
    w._city_engines = {}
    w._db_ref_cache = {}
    return w


def test_ignores_non_refresh_events():
    w = _bare_worker()
    status = w.handle_payload({"event": "article.deleted", "entity_type": "article", "entity_id": 1})
    assert status == "ignored:event"


def test_ignores_non_article_entity_type():
    w = _bare_worker()
    status = w.handle_payload(
        {"event": "article.published", "entity_type": "place", "entity_id": 1, "site_slug": "jakarta"}
    )
    assert status.startswith("ignored:entity_type")


def test_place_published_is_not_a_refresh_trigger():
    """article_search is article-only by design (migration 0006) --
    unlike now-embeddings' worker, place events must never appear in
    REFRESH_EVENTS at all."""
    assert "place.published" not in REFRESH_EVENTS
    assert "place.republished" not in REFRESH_EVENTS
    assert "article.published" in REFRESH_EVENTS
    assert "article.republished" in REFRESH_EVENTS


def test_ignores_bad_entity_id():
    w = _bare_worker()
    status = w.handle_payload(
        {"event": "article.published", "entity_type": "article", "entity_id": "not-a-number", "site_slug": "jakarta"}
    )
    assert status.startswith("ignored:bad_entity_id")


def test_ignores_unknown_site_slug():
    w = _bare_worker()
    with mock.patch.object(worker_mod, "get_site", return_value=None):
        status = w.handle_payload(
            {"event": "article.published", "entity_type": "article", "entity_id": 1, "site_slug": "nowhere"}
        )
    assert status.startswith("ignored:unknown_site_slug")


def test_ignores_entity_not_found():
    w = _bare_worker()
    fake_site = SimpleNamespace(db_ref="now_jakarta")
    with mock.patch.object(worker_mod, "get_site", return_value=fake_site), \
         mock.patch.object(worker_mod, "city_engine", return_value=mock.Mock()), \
         mock.patch.object(worker_mod, "fetch_one", return_value=None):
        status = w.handle_payload(
            {"event": "article.published", "entity_type": "article", "entity_id": 999999, "site_slug": "jakarta"}
        )
    assert status == "ignored:not_found"


def test_real_publish_drives_refresh_call():
    w = _bare_worker()
    fake_site = SimpleNamespace(db_ref="now_jakarta")
    fake_row = SimpleNamespace(article_id=13, title="hello", dek=None, body_text="", text_hash="abc")
    with mock.patch.object(worker_mod, "get_site", return_value=fake_site), \
         mock.patch.object(worker_mod, "city_engine", return_value=mock.Mock()), \
         mock.patch.object(worker_mod, "fetch_one", return_value=fake_row), \
         mock.patch.object(worker_mod, "refresh_row", return_value=True) as mock_refresh:
        status = w.handle_payload(
            {"event": "article.published", "entity_type": "article", "entity_id": 13, "site_slug": "jakarta"}
        )
    assert status == "updated"
    mock_refresh.assert_called_once()


def test_unchanged_text_is_skipped_not_updated():
    w = _bare_worker()
    fake_site = SimpleNamespace(db_ref="now_jakarta")
    fake_row = SimpleNamespace(article_id=13, title="hello", dek=None, body_text="", text_hash="abc")
    with mock.patch.object(worker_mod, "get_site", return_value=fake_site), \
         mock.patch.object(worker_mod, "city_engine", return_value=mock.Mock()), \
         mock.patch.object(worker_mod, "fetch_one", return_value=fake_row), \
         mock.patch.object(worker_mod, "refresh_row", return_value=False):
        status = w.handle_payload(
            {"event": "article.published", "entity_type": "article", "entity_id": 13, "site_slug": "jakarta"}
        )
    assert status == "skipped_unchanged"


def test_republished_is_also_a_refresh_trigger():
    assert "article.republished" in REFRESH_EVENTS


def test_group_name_distinct_from_embeddings_worker():
    """F41 acceptance criterion: separate consumer group so the two
    workers don't steal each other's messages."""
    from now_embeddings.worker import GROUP as EMBEDDINGS_GROUP

    assert worker_mod.GROUP != EMBEDDINGS_GROUP
    assert worker_mod.STREAM == "now:domain-events:stream"  # same stream, different group
