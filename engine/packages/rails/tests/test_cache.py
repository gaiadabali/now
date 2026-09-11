"""`engine.rail_cache` round-trip (F33: `article_id text`, no migration
needed -- this package writes to the real, already-shipped table, and
every test here cleans up its own rows so a real (empty-today)
`engine.rail_cache` is left exactly as it found it."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from now_rails.cache import DEFAULT_MAX_AGE, is_fresh, read_cached_rails, write_rail_cache
from now_rails.models import ComponentScoreOut, RailItem, RailResult

TEST_ARTICLE_ID = 999_999_001  # sentinel id, never a real public.articles row


def _sample_result(rail: str) -> RailResult:
    return RailResult(
        rail=rail,
        items=[
            RailItem(
                entity_type="place", entity_id=1, rail=rail, position=1, score=0.9,
                components=[ComponentScoreOut(key="geo_proximity", label="geo_proximity", value=0.9, weight=0.5, explanation="x", available=True)],
                title="Test Place", slug="test-place",
            )
        ],
        rung_name="strict", rung_index=0, rungs_evaluated=["strict"], pool_size=1,
        subject_type="stay", weights_source="test",
    )


def test_write_then_read_round_trips(city_conn):
    try:
        write_rail_cache(city_conn, TEST_ARTICLE_ID, "default", _sample_result("row1_complementary"))
        cached = read_cached_rails(city_conn, TEST_ARTICLE_ID, "default", ["row1_complementary", "row2_nearby"])

        assert set(cached.keys()) == {"row1_complementary"}
        entry = cached["row1_complementary"]
        assert entry.result.rung_name == "strict"
        assert entry.result.items[0].entity_id == 1
        assert entry.result.items[0].components[0].value == 0.9
        assert is_fresh(entry)
    finally:
        city_conn.execute(
            text("DELETE FROM engine.rail_cache WHERE article_id = :aid"), {"aid": str(TEST_ARTICLE_ID)}
        )
        city_conn.commit()


def test_stale_row_is_not_fresh(city_conn):
    try:
        stale_time = datetime.now(timezone.utc) - DEFAULT_MAX_AGE - timedelta(hours=1)
        write_rail_cache(city_conn, TEST_ARTICLE_ID, "default", _sample_result("row2_nearby"), now=stale_time)
        cached = read_cached_rails(city_conn, TEST_ARTICLE_ID, "default", ["row2_nearby"])
        assert not is_fresh(cached["row2_nearby"])
    finally:
        city_conn.execute(
            text("DELETE FROM engine.rail_cache WHERE article_id = :aid"), {"aid": str(TEST_ARTICLE_ID)}
        )
        city_conn.commit()


def test_upsert_overwrites_previous_value(city_conn):
    try:
        write_rail_cache(city_conn, TEST_ARTICLE_ID, "default", _sample_result("row3_similar"))
        second = RailResult(
            rail="row3_similar", items=[], rung_name="editorial_fallback", rung_index=3,
            rungs_evaluated=["strict", "editorial_fallback"], pool_size=0, subject_type=None,
            weights_source="test", unvalidated_reason="second write",
        )
        write_rail_cache(city_conn, TEST_ARTICLE_ID, "default", second)
        cached = read_cached_rails(city_conn, TEST_ARTICLE_ID, "default", ["row3_similar"])
        assert cached["row3_similar"].result.rung_name == "editorial_fallback"
        assert cached["row3_similar"].result.items == []
    finally:
        city_conn.execute(
            text("DELETE FROM engine.rail_cache WHERE article_id = :aid"), {"aid": str(TEST_ARTICLE_ID)}
        )
        city_conn.commit()
