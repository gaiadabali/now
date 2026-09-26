"""P1.2's acceptance, against a real Postgres: a merge round-trips
(mentions moved, the survivor keeps both names as aliases, and unmerge puts
every row back exactly).

Needs a city database with the Payload schema (migrated through
`20260927_090000_places_aliases_and_reviewed_by`). Point
`NOW_PLACES_TEST_DB` at a SCRATCH copy -- never a live city database:

    NOW_PLACES_TEST_DB=now_bali_p1_scratch uv run pytest tests/test_merge_db.py

Everything runs inside one outer transaction that is rolled back at the
end, so even the scratch copy is left as it was. Skipped when the variable
is unset (CI has no city database).
"""

from __future__ import annotations

import json
import os
import uuid

import pytest
from sqlalchemy import text

from now_places.db import apply_junk, make_engine, revert_junk
from now_places.merge import MergeRefused, apply_merge, unmerge

DB = os.environ.get("NOW_PLACES_TEST_DB")
pytestmark = pytest.mark.skipif(not DB, reason="NOW_PLACES_TEST_DB not set (needs a scratch city database)")

LIVE = {"now_bali", "now_jakarta", "now_platform"}


@pytest.fixture()
def conn():
    assert DB not in LIVE, "point NOW_PLACES_TEST_DB at a scratch copy, never a live city database"
    engine = make_engine(DB)
    c = engine.connect()
    outer = c.begin()
    try:
        yield c
    finally:
        outer.rollback()
        c.close()
        engine.dispose()


def _place(conn, name: str, status: str = "pending_review") -> int:
    slug = f"p1-test-{uuid.uuid4().hex[:10]}"
    return conn.execute(
        text(
            "insert into public.places (name, slug, type, subtype, status, source) "
            "values (:n, :s, 'editorial', 'city-guide', cast(:st as enum_places_status), 'extracted') returning id"
        ),
        {"n": name, "s": slug, "st": status},
    ).scalar()


def _mention(conn, place_id: int, article_id: int, role: str = "mentioned") -> int:
    return conn.execute(
        text(
            "insert into public.place_mentions (article_id, place_id, \"offset\", surface_text, role) "
            "values (:a, :p, 0, 'test', cast(:r as enum_place_mentions_role)) returning id"
        ),
        {"a": article_id, "p": place_id, "r": role},
    ).scalar()


def _snapshot(conn, ids: list[int]) -> dict:
    places = conn.execute(
        text("select id, name, status::text, merged_into_id, aliases from public.places where id = any(:ids) order by id"),
        {"ids": ids},
    ).all()
    mentions = conn.execute(
        text("select id, place_id from public.place_mentions where place_id = any(:ids) order by id"), {"ids": ids}
    ).all()
    return {"places": [tuple(r) for r in places], "mentions": [tuple(r) for r in mentions]}


def test_merge_round_trips(conn):
    article = conn.execute(text("select id from public.articles order by id limit 1")).scalar()
    survivor = _place(conn, "Karma Kandara")
    loser = _place(conn, "Karma Kandara Resort")
    earlier = _place(conn, "Karma Kandara Bali")  # previously merged INTO the loser
    conn.execute(text("update public.places set merged_into_id = :l where id = :e"), {"l": loser, "e": earlier})
    conn.execute(
        text("update public.places set aliases = cast(:a as jsonb) where id = :l"),
        {"a": json.dumps([{"name": "Karma Kandara Bali", "placeId": earlier}]), "l": loser},
    )
    m_loser = [_mention(conn, loser, article, "featured"), _mention(conn, loser, article)]
    m_survivor = [_mention(conn, survivor, article)]
    ids = [survivor, loser, earlier]
    before = _snapshot(conn, ids)

    rec = apply_merge(conn, loser, survivor, score=0.9, by="test")

    # mentions moved, and only the loser's
    moved = conn.execute(text("select id from public.place_mentions where place_id = :s order by id"), {"s": survivor}).scalars().all()
    assert sorted(moved) == sorted(m_loser + m_survivor)
    assert rec.mention_ids == sorted(m_loser)
    assert conn.execute(text("select count(*) from public.place_mentions where place_id = :l"), {"l": loser}).scalar() == 0
    # merged_into set; the earlier merge re-pointed at the survivor
    assert conn.execute(text("select merged_into_id from public.places where id = :l"), {"l": loser}).scalar() == survivor
    assert conn.execute(text("select merged_into_id from public.places where id = :e"), {"e": earlier}).scalar() == survivor
    assert rec.repointed_place_ids == [earlier]
    # the survivor keeps both names: its own, and the loser's (+ what the loser had absorbed)
    name, aliases = conn.execute(text("select name, aliases from public.places where id = :s"), {"s": survivor}).one()
    assert name == "Karma Kandara"
    assert aliases[-1]["name"] == "Karma Kandara Resort"
    assert aliases[-1]["placeId"] == loser
    assert aliases[-1]["inheritedAliases"] == ["Karma Kandara Bali"]
    assert aliases[-1]["mentionIds"] == sorted(m_loser)

    back = unmerge(conn, loser, by="test")
    assert back.mention_ids == sorted(m_loser)
    assert _snapshot(conn, ids) == before


def test_merge_refusals(conn):
    a = _place(conn, "Alpha")
    b = _place(conn, "Beta")
    approved = _place(conn, "Gamma", status="active")
    with pytest.raises(MergeRefused):
        apply_merge(conn, a, a, score=None, by="test")
    with pytest.raises(MergeRefused):
        apply_merge(conn, approved, b, score=None, by="test")  # never merge an approved row away
    apply_merge(conn, a, b, score=None, by="test")
    with pytest.raises(MergeRefused):
        apply_merge(conn, a, b, score=None, by="test")  # already merged
    c = _place(conn, "Delta")
    apply_merge(conn, b, c, score=None, by="test")  # b (a's survivor) is now merged itself
    with pytest.raises(MergeRefused):
        unmerge(conn, a, by="test")  # last in, first out
    unmerge(conn, b, by="test")
    unmerge(conn, a, by="test")
    assert conn.execute(text("select count(*) from public.places where id = any(:i) and merged_into_id is not null"), {"i": [a, b, c]}).scalar() == 0


def test_junk_apply_touches_only_pending_rows_and_reverts(conn):
    pending = _place(conn, "Hotel's")
    active = _place(conn, "Hotel's Terrace", status="active")
    changed = apply_junk(conn, [pending, active])
    assert changed == [pending]
    status = dict(conn.execute(text("select id, status::text from public.places where id = any(:i)"), {"i": [pending, active]}).all())
    assert status == {pending: "junk", active: "active"}
    assert revert_junk(conn, [pending]) == [pending]
    assert conn.execute(text("select status::text from public.places where id = :p"), {"p": pending}).scalar() == "pending_review"
