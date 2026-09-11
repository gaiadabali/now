"""Demonstration test (also a real assertion): the exact same mention,
same place row, walked through all three tiers by mutating only the
`engine.partnerships` row -- proving tier transitions are pure data,
never an article edit or a code change. Run with `-s` to see the
rendered HTML at each step (used for the ticket's before/after evidence)."""

from __future__ import annotations

from conftest import SYNTH_PLACES_TABLE, make_partnership, make_place
from sqlalchemy import text

from now_link_resolver.render import render_body_blocks
from now_link_resolver.resolver import resolve_mention

MENTION_HTML = 'We stayed at <span data-place="{pid}">The Viceroy Bali</span> for three nights.'


def _resolve_and_render(city_conn, platform_conn, site_id, place_id):
    decision = resolve_mention(
        city_conn, platform_conn, site_id=site_id, place_id=place_id, places_table=SYNTH_PLACES_TABLE
    )
    blocks = [{"type": "paragraph", "html": MENTION_HTML.format(pid=place_id)}]
    html = render_body_blocks(blocks, {place_id: decision})[0]["html"]
    return decision, html


def test_same_mention_across_all_three_tiers_and_an_expiry_boundary(city_conn, platform_conn, site_id, capsys):
    place_id = make_place(city_conn, slug="viceroy-bali", name="The Viceroy Bali")

    # 1. free -- no partnership at all yet.
    free_decision, free_html = _resolve_and_render(city_conn, platform_conn, site_id, place_id)
    assert free_decision.tier == "free"
    assert "<a " not in free_html

    # 2. listed -- org/place signs a listed-tier deal.
    partnership_id = make_partnership(platform_conn, site_id=site_id, tier="listed", place_id=place_id)
    listed_decision, listed_html = _resolve_and_render(city_conn, platform_conn, site_id, place_id)
    assert listed_decision.tier == "listed"
    assert '<a href="/places/viceroy-bali">' in listed_html
    assert "rel=" not in listed_html

    # 3. paid -- upgrades to paid (same row, admin flips tier + adds a url).
    platform_conn.execute(
        text(
            "UPDATE engine.partnerships SET tier = 'paid', custom_url = :url, "
            "show_badge = true, badge_label = 'Presented by' WHERE id = :id"
        ),
        {"url": "https://partner.example/viceroy?utm=now", "id": partnership_id},
    )
    paid_decision, paid_html = _resolve_and_render(city_conn, platform_conn, site_id, place_id)
    assert paid_decision.tier == "paid"
    assert 'rel="sponsored"' in paid_html
    assert 'href="https://partner.example/viceroy?utm=now"' in paid_html

    # 4. expiry boundary -- the contract lapses; same row, only ends_at changes.
    platform_conn.execute(
        text("UPDATE engine.partnerships SET ends_at = now() - interval '1 minute' WHERE id = :id"),
        {"id": partnership_id},
    )
    lapsed_decision, lapsed_html = _resolve_and_render(city_conn, platform_conn, site_id, place_id)
    assert lapsed_decision.tier == "free"
    assert "<a " not in lapsed_html

    with capsys.disabled():
        print("\n--- E4.2 tier ladder demo: same mention, same place row ---")
        print("1. FREE   (no partnership):      ", free_html)
        print("2. LISTED (place-level deal):     ", listed_html)
        print("3. PAID   (upgraded, same row):   ", paid_html)
        print("4. EXPIRED (ends_at in the past): ", lapsed_html)
