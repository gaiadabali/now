"""Unit tests for the routing/filtering logic in `ReembedWorker.handle_payload`
-- no real Redis or Postgres. `ReembedWorker.__init__` opens a real Redis
connection (`ensure_group`) and a real platform DB engine, so tests build
the instance via `object.__new__` and set only the attributes
`handle_payload` actually reads, then monkeypatch the module-level
`get_site`/`fetch_one`/`reembed_one`/`city_engine` names it calls.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import now_embeddings.worker as worker_mod
from now_embeddings.worker import REEMBED_EVENTS, ReembedWorker


def _bare_worker() -> ReembedWorker:
    w = object.__new__(ReembedWorker)
    w.provider = SimpleNamespace(name="fake-model", dim=4)
    w._platform_engine = mock.MagicMock()
    w._city_engines = {}
    w._db_ref_cache = {}
    return w


def test_ignores_non_reembed_events():
    w = _bare_worker()
    status = w.handle_payload({"event": "article.deleted", "entity_type": "article", "entity_id": 1})
    assert status == "ignored:event"


def test_ignores_unsupported_entity_type():
    w = _bare_worker()
    status = w.handle_payload({"event": "article.published", "entity_type": "event", "entity_id": 1, "site_slug": "jakarta"})
    assert status.startswith("ignored:entity_type")


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


def test_real_publish_drives_reembed_call():
    w = _bare_worker()
    fake_site = SimpleNamespace(db_ref="now_jakarta")
    fake_row = SimpleNamespace(entity_type="article", entity_id="13", text="hello", text_hash="abc")
    with mock.patch.object(worker_mod, "get_site", return_value=fake_site), \
         mock.patch.object(worker_mod, "city_engine", return_value=mock.Mock()), \
         mock.patch.object(worker_mod, "fetch_one", return_value=fake_row), \
         mock.patch.object(worker_mod, "reembed_one", return_value=True) as mock_reembed:
        status = w.handle_payload(
            {"event": "article.published", "entity_type": "article", "entity_id": 13, "site_slug": "jakarta"}
        )
    assert status == "reembedded"
    mock_reembed.assert_called_once()


def test_unchanged_text_is_skipped_not_reembedded():
    w = _bare_worker()
    fake_site = SimpleNamespace(db_ref="now_jakarta")
    fake_row = SimpleNamespace(entity_type="article", entity_id="13", text="hello", text_hash="abc")
    with mock.patch.object(worker_mod, "get_site", return_value=fake_site), \
         mock.patch.object(worker_mod, "city_engine", return_value=mock.Mock()), \
         mock.patch.object(worker_mod, "fetch_one", return_value=fake_row), \
         mock.patch.object(worker_mod, "reembed_one", return_value=False):
        status = w.handle_payload(
            {"event": "article.published", "entity_type": "article", "entity_id": 13, "site_slug": "jakarta"}
        )
    assert status == "skipped_unchanged"


def test_republished_is_also_a_reembed_trigger():
    assert "article.republished" in REEMBED_EVENTS
    assert "place.published" in REEMBED_EVENTS
