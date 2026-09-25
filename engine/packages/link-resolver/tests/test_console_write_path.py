"""Proves `now_link_resolver` picks up a partnership written by the console
(S5.2) on the request path -- ARCHITECTURE.md §11's mission for this
ticket: "Prove `now_link_resolver` picks the partnership up on the request
path... or use the resolver's own tests against the real row."

`place_mentions` is empty archive-wide (E2.3 is blocked -- PROGRESS.md), so
there is no real article anywhere that mentions a real org today, and
"render a real article" is not a thing this repository can currently do.
This is the ticket's own named alternative: insert a row shaped EXACTLY
like the one `apps/web/src/lib/queries.ts`'s `createPartnership` writes --
same columns, same values a console save would produce, including the
fields that ticket's write form exposes (`show_badge`, `badge_label`,
`custom_url`) -- against the REAL `engine.partnerships` table (not a
synthetic one; see conftest.py's `platform_conn`, one rolled-back
transaction per test, nothing committed, safe alongside concurrent agents),
and confirm `resolve_mention` reads it back through the real
`engine.partnerships_active` view and applies the real tier ladder.

This is a stronger claim than "the resolver's existing tests pass" -- those
(`test_resolver.py`) were written before this ticket and already prove the
lookup logic. This file's job is narrower and specific to S5.2: the EXACT
row shape the new write path produces resolves correctly, end to end,
through code neither file shares.
"""

from __future__ import annotations

from conftest import SYNTH_PLACES_TABLE, make_place

from now_link_resolver.render import render_body_blocks
from now_link_resolver.resolver import resolve_mention


def _console_shaped_partnership(
    conn,
    *,
    site_id: str,
    org_id: str,
    tier: str,
    custom_url: str | None = None,
    show_badge: bool = False,
    badge_label: str | None = None,
):
    """Insert exactly the column set `createPartnership` in
    `apps/web/src/lib/queries.ts` writes on a console save, including the
    fields that function sets which `conftest.py`'s own `make_partnership`
    helper does not exercise by default (`link_policy`, `itinerary_eligible`,
    `boost_cap`) -- so this test's row is not merely *a* partnership, it is
    the specific shape S5.2's form produces.
    """
    from sqlalchemy import text

    result = conn.execute(
        text(
            """
            INSERT INTO engine.partnerships
                (org_id, site_id, tier, status, link_policy, custom_url, utm_template,
                 show_badge, badge_label, itinerary_eligible, boost_cap)
            VALUES
                (:org_id, :site_id, :tier, 'active', '{}'::jsonb, :custom_url, 'utm_source=now',
                 :show_badge, :badge_label, true, 0.2)
            RETURNING id::text
            """
        ),
        {
            "org_id": org_id,
            "site_id": site_id,
            "tier": tier,
            "custom_url": custom_url,
            "show_badge": show_badge,
            "badge_label": badge_label,
        },
    )
    return result.scalar_one()


def test_console_created_paid_partnership_resolves_sponsored_on_request_path(
    city_conn, platform_conn, site_id
):
    """The exact scenario ARCHITECTURE.md §11 describes: an org signs a paid
    deal, and every existing mention of one of its venues becomes a
    `rel="sponsored"` link with a badge -- with NO article edit, because the
    resolver reads the partnership at render time."""
    from conftest import make_org

    org_id = make_org(platform_conn, name="WS4 Test Hotel Group")
    partnership_id = _console_shaped_partnership(
        platform_conn,
        site_id=site_id,
        org_id=org_id,
        tier="paid",
        custom_url="https://partner.example/ws4-test?utm=now",
        show_badge=True,
        badge_label="Partner",
    )
    place_id = make_place(city_conn, org_id=org_id, slug="ws4-test-venue", name="WS4 Test Venue")

    decision = resolve_mention(
        city_conn, platform_conn, site_id=site_id, place_id=place_id, places_table=SYNTH_PLACES_TABLE
    )

    assert decision.tier == "paid"
    assert decision.partnership_id == partnership_id
    assert decision.org_id == org_id
    assert decision.href == "https://partner.example/ws4-test?utm=now"
    # The one line E4.2 exists to guarantee, computed from tier alone —
    # never read off a column the console wrote.
    assert decision.rel == "sponsored"
    assert decision.show_badge is True
    assert decision.badge_label == "Partner"
    assert decision.resolved_via == "org"

    # And the renderer — the other half of "the request path" — turns that
    # decision into the actual HTML an article page serves, unprompted by
    # anything except the resolved decision.
    body = [{"type": "paragraph", "html": '<span data-place="{}">WS4 Test Venue</span> is lovely.'.format(place_id)}]
    rendered = render_body_blocks(body, {place_id: decision})
    html = rendered[0]["html"]
    assert 'rel="sponsored"' in html
    assert f'data-partnership="{partnership_id}"' in html
    assert 'class="badge badge--partner"' in html


def test_console_created_listed_partnership_resolves_internal_link(city_conn, platform_conn, site_id):
    """The console's 'listed' tier — internal `/places/{slug}` link, no
    `rel="sponsored"` (§11's tier ladder: only 'paid' gets that)."""
    from conftest import make_org

    org_id = make_org(platform_conn, name="WS4 Test Cafe Co")
    _console_shaped_partnership(platform_conn, site_id=site_id, org_id=org_id, tier="listed")
    place_id = make_place(city_conn, org_id=org_id, slug="ws4-test-cafe", name="WS4 Test Cafe")

    decision = resolve_mention(
        city_conn, platform_conn, site_id=site_id, place_id=place_id, places_table=SYNTH_PLACES_TABLE
    )

    assert decision.tier == "listed"
    assert decision.href == "/places/ws4-test-cafe"
    assert decision.rel is None
    assert decision.resolved_via == "org"


def test_console_created_ended_status_partnership_does_not_resolve(city_conn, platform_conn, site_id):
    """S5.2's write form lets status become 'ended' — proving the resolver's
    `engine.partnerships_active` view (query-time liveness, not this
    package's job to re-derive) actually stops honouring a row the console
    ended, not merely that the row still exists."""
    from sqlalchemy import text

    from conftest import make_org

    org_id = make_org(platform_conn, name="WS4 Test Ended Co")
    platform_conn.execute(
        text(
            """
            INSERT INTO engine.partnerships (org_id, site_id, tier, status, custom_url)
            VALUES (:org_id, :site_id, 'paid', 'ended', 'https://ended.example')
            """
        ),
        {"org_id": org_id, "site_id": site_id},
    )
    place_id = make_place(city_conn, org_id=org_id, slug="ws4-test-ended", name="WS4 Test Ended Venue")

    decision = resolve_mention(
        city_conn, platform_conn, site_id=site_id, place_id=place_id, places_table=SYNTH_PLACES_TABLE
    )

    assert decision.tier == "free"
    assert decision.resolved_via == "none"
