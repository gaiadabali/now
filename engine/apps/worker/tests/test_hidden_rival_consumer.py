"""Dispatch tests for the hidden-rival recompute handler
(`app.consumer.DomainEventWorker._handle_hidden_rival`) -- WS1 third pass.

Same faked-engine style as `test_classification.py`: the behaviour worth
testing here is DISPATCH (which events reach the handler, that re-embed
still runs alongside it, that an unknown site slug or a raised exception
is reported rather than left to crash the consumer loop), not "does it run
the right SQL" -- that is `now_filters.hidden_rival_recompute`'s own job
and its own tests (`test_hidden_rival_recompute_db.py`, real Postgres via
synthetic tables). `now_filters.hidden_rival_recompute.recompute_flags_for_article`
/ `remove_flags_for_article` are monkeypatched here so this file needs no
database at all.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app import consumer as consumer_module
from app.consumer import DomainEventWorker


def worker(**attrs) -> DomainEventWorker:
    """A `DomainEventWorker` with no `__init__` -- see `test_classification
    .py`'s identical helper for why (the real constructor opens Redis and
    two Postgres pools)."""
    instance = object.__new__(DomainEventWorker)
    instance.apply_classification_reviews = True
    instance._facet_shapes = {}
    for name, value in attrs.items():
        setattr(instance, name, value)
    return instance


class FakeEngine:
    """`engine.begin()` as a no-op context manager -- the handler never
    inspects the connection object itself, only passes it through to the
    (monkeypatched) recompute functions."""

    def __init__(self) -> None:
        self.opened = 0

    def begin(self):
        self.opened += 1

        class _Transaction:
            def __enter__(self):
                return "fake-connection"

            def __exit__(self, *exc):
                return False

        return _Transaction()


def event_for(**overrides) -> dict:
    base = dict(event="article.published", site_slug="alpha", entity_type="article", entity_id="4429")
    base.update(overrides)
    return base


@dataclass(frozen=True)
class FakeArticleReport:
    added: int = 1
    removed: int = 0
    unchanged: int = 0


def test_publish_recomputes_flags_and_still_reaches_the_re_embed_handler(monkeypatch):
    """The handler is additive, same requirement as classification's own
    `test_other_events_still_reach_the_re_embed_handler` -- breaking
    `article.published`'s re-embed to add this would trade one silent gap
    for another."""
    calls = []
    monkeypatch.setattr(
        consumer_module, "recompute_flags_for_article", lambda conn, article_id: calls.append(("recompute", article_id)) or FakeArticleReport(added=2)
    )
    seen_by_base = []
    monkeypatch.setattr(
        consumer_module.ReembedWorker, "handle_payload", lambda self, event: seen_by_base.append(event) or "reembedded"
    )

    engine = FakeEngine()
    instance = worker(_engine_for_slug=lambda slug: engine)
    status = instance.handle_payload(event_for())

    assert calls == [("recompute", "4429")]
    assert len(seen_by_base) == 1, "the base class's re-embed handler must still run"
    assert status == "reembedded+hidden_rival:added=2 removed=0"


def test_republish_also_recomputes(monkeypatch):
    calls = []
    monkeypatch.setattr(
        consumer_module, "recompute_flags_for_article", lambda conn, article_id: calls.append(article_id) or FakeArticleReport()
    )
    monkeypatch.setattr(consumer_module.ReembedWorker, "handle_payload", lambda self, event: "skipped_unchanged")
    instance = worker(_engine_for_slug=lambda slug: FakeEngine())
    instance.handle_payload(event_for(event="article.republished"))
    assert calls == ["4429"]


def test_unpublish_removes_flags_without_calling_recompute(monkeypatch):
    recompute_calls = []
    remove_calls = []
    monkeypatch.setattr(consumer_module, "recompute_flags_for_article", lambda conn, article_id: recompute_calls.append(article_id))
    monkeypatch.setattr(consumer_module, "remove_flags_for_article", lambda conn, article_id: remove_calls.append(article_id) or 3)
    # `article.unpublished` is not in the base class's REEMBED_EVENTS, so
    # its real `handle_payload` already returns `ignored:event` for it —
    # no need to monkeypatch the base class for this one.
    instance = worker(_engine_for_slug=lambda slug: FakeEngine())
    status = instance.handle_payload(event_for(event="article.unpublished"))

    assert remove_calls == ["4429"]
    assert recompute_calls == []
    assert status == "ignored:event+hidden_rival:removed=3"


def test_unknown_site_slug_is_acked_without_touching_a_database(monkeypatch):
    monkeypatch.setattr(consumer_module.ReembedWorker, "handle_payload", lambda self, event: "ignored:unknown_site_slug=ghost")
    instance = worker(_engine_for_slug=lambda slug: None)
    status = instance.handle_payload(event_for(site_slug="ghost"))
    assert "hidden_rival:ignored:unknown_site_slug=ghost" in status


def test_a_non_article_entity_type_is_a_defensive_no_op(monkeypatch):
    monkeypatch.setattr(consumer_module.ReembedWorker, "handle_payload", lambda self, event: "reembedded")
    instance = worker(_engine_for_slug=lambda slug: FakeEngine())
    status = instance.handle_payload(event_for(entity_type="place"))
    assert "hidden_rival:ignored:entity_type=place" in status


def test_a_recompute_failure_is_reported_not_raised(monkeypatch):
    """A DB blip recomputing hidden-rival flags must not crash the whole
    message and lose the (successful) re-embed alongside it — same stance
    `_handle_classification_reviewed` takes for an unusable event."""

    def boom(conn, article_id):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(consumer_module, "recompute_flags_for_article", boom)
    monkeypatch.setattr(consumer_module.ReembedWorker, "handle_payload", lambda self, event: "reembedded")
    instance = worker(_engine_for_slug=lambda slug: FakeEngine())
    status = instance.handle_payload(event_for())
    assert status == "reembedded+hidden_rival:error"


def test_other_events_are_unaffected(monkeypatch):
    seen = []
    monkeypatch.setattr(consumer_module.ReembedWorker, "handle_payload", lambda self, event: seen.append(event) or "ignored:event")
    instance = worker()
    assert instance.handle_payload({"event": "place.published"}) == "ignored:event"
    assert len(seen) == 1
