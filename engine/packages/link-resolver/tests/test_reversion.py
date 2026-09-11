"""The headline behaviour: 'a contract lapses -> it reverts automatically
at ends_at, with no job run.' Proven by resolving the *same* mention
against the *same* partnership row, changing only `ends_at`/`starts_at`
via a plain UPDATE, and re-resolving with the exact same code path --
no cache to bust, no job to run, no code change between the two calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import SYNTH_PLACES_TABLE, make_partnership, make_place
from sqlalchemy import text

from now_link_resolver.render import render_body_blocks
from now_link_resolver.resolver import resolve_mention

BLOCKS = [{"type": "paragraph", "html": 'Stayed at <span data-place="{pid}">The Viceroy</span> for a week.'}]


def _resolve(city_conn, platform_conn, site_id, place_id):
    return resolve_mention(
        city_conn, platform_conn, site_id=site_id, place_id=place_id, places_table=SYNTH_PLACES_TABLE
    )


def _render(decision, place_id):
    blocks = [{"type": "paragraph", "html": BLOCKS[0]["html"].format(pid=place_id)}]
    return render_body_blocks(blocks, {place_id: decision})[0]["html"]


def test_reverts_to_plain_text_the_instant_ends_at_is_in_the_past(city_conn, platform_conn, site_id):
    place_id = make_place(city_conn, slug="viceroy-bali", name="The Viceroy Bali")
    now = datetime.now(timezone.utc)

    partnership_id = make_partnership(
        platform_conn,
        site_id=site_id,
        tier="paid",
        place_id=place_id,
        custom_url="https://partner.example/viceroy",
        starts_at=(now - timedelta(days=400)).isoformat(),
        ends_at=(now + timedelta(days=1)).isoformat(),  # still live
    )

    before = _resolve(city_conn, platform_conn, site_id, place_id)
    before_html = _render(before, place_id)
    assert before.tier == "paid"
    assert 'rel="sponsored"' in before_html
    assert 'href="https://partner.example/viceroy"' in before_html

    # The contract lapses: an admin (or, in reality, time itself) moves
    # ends_at into the past. No application code changes, no cache is
    # invalidated, no batch job runs between this UPDATE and the next
    # resolve() call below.
    platform_conn.execute(
        text("UPDATE engine.partnerships SET ends_at = :ends_at WHERE id = :id"),
        {"ends_at": (now - timedelta(minutes=1)).isoformat(), "id": partnership_id},
    )

    after = _resolve(city_conn, platform_conn, site_id, place_id)
    after_html = _render(after, place_id)

    assert after.tier == "free"
    assert after.href is None
    assert after.rel is None
    assert "<a " not in after_html
    assert "The Viceroy" in after_html  # surface text survives, just unlinked

    print("BEFORE (paid, live):", before_html)
    print("AFTER  (lapsed, ends_at in the past):", after_html)


def test_a_signed_partner_lights_up_instantly_no_article_edit(city_conn, platform_conn, site_id):
    """The inverse of the lapse case: a brand-new partnership on an
    existing mention (standing in for 'a partner signs today') makes the
    very next render() call a paid link, with the article's body_blocks
    never touched."""
    place_id = make_place(city_conn, slug="warung-new-partner", name="Warung New Partner")

    before = _resolve(city_conn, platform_conn, site_id, place_id)
    assert before.tier == "free"  # no partnership yet -- pre-existing historical mention

    make_partnership(
        platform_conn,
        site_id=site_id,
        tier="paid",
        place_id=place_id,
        custom_url="https://warung-new-partner.example",
    )

    after = _resolve(city_conn, platform_conn, site_id, place_id)
    assert after.tier == "paid"
    assert 'rel="sponsored"' in _render(after, place_id)
