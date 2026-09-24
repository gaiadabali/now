"""Tests for the `classification.reviewed` handler.

The behaviour worth testing here is not "does it run SQL" — it is the three
decisions the handler makes that a reviewer's work depends on:

  * which rows count as *superseded*, which differs by facet cardinality and
    is the difference between an article tagged `drink` and an article
    tagged both `eat` and `drink`;
  * which events are refused rather than half-applied;
  * that a redelivered message cannot corrupt state.

The engine is faked rather than mocked through SQLAlchemy's own machinery so
the assertions can be about the *statements*, which is where the behaviour
lives. The round trip against real Postgres is `scripts/verify-classification
-reviewed.py`, which is the proof; this is the fast feedback.
"""

from __future__ import annotations

import pytest

from app import classification
from app.classification import Decision, FacetShape, UnusableEvent, apply_decision, decision_from
from app.consumer import DomainEventWorker

TYPE_TERMS = ["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"]
EAT, DRINK = TYPE_TERMS
AREA_A = "33333333-3333-3333-3333-333333333333"
AREA_B = "44444444-4444-4444-4444-444444444444"

SINGLE_FACET = FacetShape(cardinality="single", term_ids=TYPE_TERMS)
MULTI_FACET = FacetShape(cardinality="multi", term_ids=[AREA_A, AREA_B])


# ---------------------------------------------------------------------------
# A fake Engine that records statements
# ---------------------------------------------------------------------------


class FakeResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class RecordingConnection:
    def __init__(self, rowcount: int) -> None:
        self.statements: list[tuple[str, dict]] = []
        self._rowcount = rowcount

    def execute(self, stmt, params=None):
        self.statements.append((" ".join(str(stmt).split()), params or {}))
        return FakeResult(self._rowcount)


class RecordingEngine:
    """Only `begin()` — deliberately. `apply_decision` opening a `connect()`
    instead of a transaction would mean the supersede and the write could not
    both be rolled back, and this fake fails loudly if it ever does."""

    def __init__(self, rowcount: int = 1) -> None:
        self.connection = RecordingConnection(rowcount)
        self.transactions = 0

    def begin(self):
        self.transactions += 1
        connection = self.connection

        class _Transaction:
            def __enter__(self):
                return connection

            def __exit__(self, *exc):
                return False

        return _Transaction()

    @property
    def statements(self) -> list[tuple[str, dict]]:
        return self.connection.statements


def decision(**overrides) -> Decision:
    base = dict(
        site_slug="alpha",
        entity_type="article",
        entity_id="4821",
        facet_key="type",
        review_id=7,
        term_id=DRINK,
        previous_term_id=EAT,
        value="drink",
        review_state="corrected",
        confidence=1.0,
    )
    base.update(overrides)
    return Decision(**base)


def only(statements, needle: str) -> list[tuple[str, dict]]:
    return [s for s in statements if needle in s[0]]


# ---------------------------------------------------------------------------
# Supersession — the case the whole ticket turns on
# ---------------------------------------------------------------------------


def test_correcting_a_single_valued_facet_retires_every_other_term_in_it():
    """An article must not end up tagged both `eat` and `drink`.

    Scoped to the facet, not to `previous_term_id`: that field is the AI's
    ORIGINAL proposal frozen on the review row, so a second correction of the
    same review reports the first guess again and a `previous_term_id` delete
    would leave the intermediate term behind forever.
    """

    engine = RecordingEngine(rowcount=1)
    assert apply_decision(engine, SINGLE_FACET, decision()) == "applied"

    deletes = only(engine.statements, "delete from engine.entity_terms")
    assert len(deletes) == 1
    sql, params = deletes[0]
    assert "term_id = any(cast(:facet_term_ids as uuid[]))" in sql
    assert "term_id <> cast(:keep_term_id as uuid)" in sql
    assert params["facet_term_ids"] == TYPE_TERMS
    assert params["keep_term_id"] == DRINK, "the term just decided must survive its own cleanup"


def test_multi_valued_facet_only_retires_the_term_the_event_names():
    """`location` is `multi` in the platform vocabulary: an article can sit in
    two neighbourhoods legitimately. Facet-wide supersession here would delete
    co-assigned areas nobody reviewed."""

    engine = RecordingEngine(rowcount=1)
    apply_decision(engine, MULTI_FACET, decision(facet_key="location", term_id=AREA_B, previous_term_id=AREA_A))

    deletes = only(engine.statements, "delete from engine.entity_terms")
    assert len(deletes) == 1
    sql, params = deletes[0]
    assert "cast(:previous_term_id as uuid)" in sql
    assert "facet_term_ids" not in sql
    assert params["previous_term_id"] == AREA_A


def test_multi_valued_facet_with_nothing_superseded_deletes_nothing():
    engine = RecordingEngine()
    apply_decision(engine, MULTI_FACET, decision(facet_key="location", term_id=AREA_B, previous_term_id=None))
    assert only(engine.statements, "delete from") == []


def test_confirming_the_ai_still_rewrites_the_row_as_editor_sourced():
    """`accepted` is not a no-op. The term does not change, but `source` moves
    from `ai` to `editor` and that is the whole point: `now_blender.decay`
    trusts an editor row unconditionally and gates every other source on a
    0.85 confidence that none of this archive's rows clear."""

    engine = RecordingEngine(rowcount=0)
    assert apply_decision(engine, SINGLE_FACET, decision(term_id=EAT, previous_term_id=None, review_state="accepted", value="eat")) == "applied"

    upserts = only(engine.statements, "insert into engine.entity_terms")
    assert len(upserts) == 1
    sql, params = upserts[0]
    assert "'editor'" in sql
    assert params["term_id"] == EAT


def test_rejecting_with_no_term_retracts_instead_of_leaving_the_guess():
    """`unclassifiable` on a facet with no sentinel term (e.g. `format`)
    carries no `term_id` and no `value`. The honest end state is no row —
    leaving the classifier's debunked guess standing would present it as
    still endorsed."""

    engine = RecordingEngine(rowcount=1)
    status = apply_decision(
        engine,
        SINGLE_FACET,
        decision(term_id=None, value=None, review_state="unclassifiable", confidence=None),
    )

    assert status == "retracted"
    assert only(engine.statements, "insert into") == [], "nothing to write when there is no term"
    sql, params = only(engine.statements, "delete from engine.entity_terms")[0]
    assert "keep_term_id" not in sql
    assert params["facet_term_ids"] == TYPE_TERMS


# ---------------------------------------------------------------------------
# Idempotency and the no-clobber asymmetry
# ---------------------------------------------------------------------------


def test_the_write_is_an_upsert_so_redelivery_cannot_duplicate_or_fail():
    engine = RecordingEngine()
    apply_decision(engine, SINGLE_FACET, decision())
    sql, _ = only(engine.statements, "insert into engine.entity_terms")[0]
    assert "on conflict (entity_type, entity_id, term_id) do update" in sql


def test_replaying_the_same_event_issues_identical_statements():
    """Redelivery is a property of the stream, not an exception. Both
    statements are defined by the end state, so the second delivery asks for
    exactly what the first one asked for."""

    first, second = RecordingEngine(), RecordingEngine()
    event = decision()
    apply_decision(first, SINGLE_FACET, event)
    apply_decision(second, SINGLE_FACET, event)
    assert first.statements == second.statements


def test_the_editor_write_is_not_guarded_against_editor_rows():
    """`now_classifier.db`'s upsert carries `WHERE source <> 'editor'` so a
    machine can never overwrite a human. Copying that predicate here would
    make a human's SECOND decision a silent no-op — the same guard aimed at
    the one writer it must never block."""

    engine = RecordingEngine()
    apply_decision(engine, SINGLE_FACET, decision())
    sql, _ = only(engine.statements, "insert into engine.entity_terms")[0]
    assert "source <> 'editor'" not in sql


def test_supersede_and_write_share_one_transaction():
    """A crash between them would leave an entity with no row for a facet it
    has a decision for — worse than either end state."""

    engine = RecordingEngine()
    apply_decision(engine, SINGLE_FACET, decision())
    assert engine.transactions == 1
    assert len(engine.statements) == 2


# ---------------------------------------------------------------------------
# Reading the event
# ---------------------------------------------------------------------------


def event_for(**payload_overrides) -> dict:
    payload = {
        "review_id": 7,
        "facet_key": "type",
        "term_id": DRINK,
        "previous_term_id": EAT,
        "value": "drink",
        "review_state": "corrected",
        "source": "editor",
        "confidence": 1,
        "reviewed_by": 3,
        "reviewed_at": "2026-09-17T00:00:00.000Z",
    }
    payload.update(payload_overrides)
    return {
        "event": "classification.reviewed",
        "site_slug": "alpha",
        "entity_type": "article",
        "entity_id": 4821,
        "occurred_at": "2026-09-17T00:00:00.000Z",
        "payload": payload,
    }


def test_entity_id_is_read_as_text_because_the_column_is_text():
    """Payload ids are integer serials (migration 0005 widened this column to
    `text` for exactly that reason). JSON delivers a number; the comparison
    in every statement here is against text."""
    assert decision_from(event_for()).entity_id == "4821"


def test_a_value_with_no_term_id_is_refused_rather_than_applied():
    """The reviewer decided something real and the CMS could not map it to a
    platform term. Untagging the article on the strength of a failed lookup
    turns a vocabulary gap into data loss."""

    with pytest.raises(UnusableEvent, match="vocabulary gap"):
        decision_from(event_for(term_id=None, value="speakeasy"))


def test_a_decision_with_neither_term_nor_value_is_a_retraction_not_an_error():
    parsed = decision_from(event_for(term_id=None, value=None, review_state="unclassifiable", confidence=None))
    assert parsed.term_id is None and parsed.confidence is None


@pytest.mark.parametrize("missing", ["entity_id", "entity_type"])
def test_an_event_missing_its_subject_is_unusable(missing):
    event = event_for()
    event[missing] = None
    with pytest.raises(UnusableEvent):
        decision_from(event)


def test_a_missing_facet_key_is_unusable():
    with pytest.raises(UnusableEvent, match="facet_key"):
        decision_from(event_for(facet_key=None))


def test_a_null_confidence_still_writes_a_human_confidence():
    """`unclassifiable` on `type` resolves to the seeded `unknown` sentinel and
    carries `confidence: null`. Writing NULL would read, to anything gating on
    the number rather than on `source`, as unverifiable provenance — and fail
    closed on a decision a human was certain about."""

    engine = RecordingEngine()
    apply_decision(engine, SINGLE_FACET, decision(confidence=None, term_id=EAT, review_state="unclassifiable", value="unknown"))
    _, params = only(engine.statements, "insert into")[0]
    assert params["confidence"] == classification.EDITOR_CONFIDENCE


# ---------------------------------------------------------------------------
# Dispatch — a poison message must not stall the stream
# ---------------------------------------------------------------------------


def worker(**attrs) -> DomainEventWorker:
    """A `DomainEventWorker` with no `__init__`.

    The real constructor opens Redis and two Postgres pools and creates a
    consumer group. Dispatch has nothing to do with any of that, and a test
    that needs a live stack to assert "an unknown site slug is ACKed" is a
    test nobody runs.
    """

    instance = object.__new__(DomainEventWorker)
    instance.apply_classification_reviews = True
    instance._facet_shapes = {}
    for name, value in attrs.items():
        setattr(instance, name, value)
    return instance


def test_other_events_still_reach_the_re_embed_handler(monkeypatch):
    """The classification handler is additive. Breaking `article.published`
    to deliver it would trade one silent gap for another.

    `article.published` also reaches the hidden-rival recompute handler
    now (WS1 third pass, `app/consumer.py`'s own `HIDDEN_RIVAL_RECOMPUTE_EVENTS`)
    -- this bare event has no `entity_type`/`entity_id`, so that handler's
    own dispatch tests (`test_hidden_rival_consumer.py`) cover the real
    behaviour; this test only needs to keep proving re-embed still runs
    alongside it, hence the `+hidden_rival:...` suffix rather than the
    exact re-embed handler's own return value."""

    from now_embeddings.worker import ReembedWorker

    seen = []
    monkeypatch.setattr(
        ReembedWorker, "handle_payload", lambda self, event: seen.append(event) or "reembedded"
    )
    assert worker().handle_payload({"event": "article.published"}) == "reembedded+hidden_rival:ignored:entity_type=None"
    assert len(seen) == 1


def test_a_malformed_decision_is_reported_and_acked_not_raised():
    """`run_once` ACKs in a `finally`, so a raise here would still be ACKed —
    but it would also be logged as an error with a traceback, which reads as
    "retry this". There is nothing to retry."""

    status = worker().handle_payload({"event": "classification.reviewed", "payload": {}})
    assert status.startswith("ignored:unusable")


def test_an_unknown_site_slug_is_acked_without_touching_a_database():
    """Same stance the re-embed handler already takes: a config problem on the
    publishing side must not wedge a consumer group shared with it."""

    instance = worker(_engine_for_slug=lambda slug: None)
    status = instance.handle_payload(event_for())
    assert status.startswith("ignored:unknown_site_slug")


def test_a_facet_absent_from_the_vocabulary_is_acked():
    engine = RecordingEngine()
    instance = worker(_engine_for_slug=lambda slug: engine)
    instance._facet_shapes = {"type": None}
    assert instance.handle_payload(event_for()).startswith("ignored:unknown_facet")
    assert engine.statements == []


def test_the_handler_can_be_switched_off_without_stopping_re_embedding():
    instance = worker()
    instance.apply_classification_reviews = False
    assert instance.handle_payload(event_for()) == "ignored:classification_disabled"


def test_the_facet_shape_is_looked_up_once_per_facet(monkeypatch):
    """A reviewer clearing a queue emits one event per click; a platform round
    trip per click to re-read eleven seeded rows would dominate the path."""

    calls = []
    monkeypatch.setattr(
        classification,
        "load_facet_shape",
        lambda platform, facet_key: calls.append(facet_key) or SINGLE_FACET,
    )
    instance = worker(_engine_for_slug=lambda slug: RecordingEngine(), _platform_engine=object())
    instance.handle_payload(event_for())
    instance.handle_payload(event_for(review_id=8))
    assert calls == ["type"]
