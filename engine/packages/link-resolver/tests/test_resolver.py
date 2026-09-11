"""Proves the two-lookup resolution: place-level first, org-level
fallback, each tier's outcome, and F62's tie-break -- all against real
Postgres (synthetic place/org/partnership rows, per conftest.py)."""

from __future__ import annotations

from conftest import SYNTH_PLACES_TABLE, make_org, make_partnership, make_place

from now_link_resolver.resolver import resolve_mention


def test_free_tier_when_no_partnership_at_all(city_conn, platform_conn, site_id):
    place_id = make_place(city_conn, slug="warung-no-deal", name="Warung No Deal")
    decision = resolve_mention(
        city_conn, platform_conn, site_id=site_id, place_id=place_id, places_table=SYNTH_PLACES_TABLE
    )
    assert decision.tier == "free"
    assert decision.href is None
    assert decision.rel is None
    assert decision.resolved_via == "none"


def test_listed_tier_place_level(city_conn, platform_conn, site_id):
    place_id = make_place(city_conn, slug="cafe-listed", name="Cafe Listed")
    make_partnership(platform_conn, site_id=site_id, tier="listed", place_id=place_id)
    decision = resolve_mention(
        city_conn, platform_conn, site_id=site_id, place_id=place_id, places_table=SYNTH_PLACES_TABLE
    )
    assert decision.tier == "listed"
    assert decision.href == "/places/cafe-listed"
    assert decision.rel is None
    assert decision.resolved_via == "place"


def test_paid_tier_place_level_with_badge(city_conn, platform_conn, site_id):
    place_id = make_place(city_conn, slug="viceroy-bali", name="The Viceroy Bali")
    make_partnership(
        platform_conn,
        site_id=site_id,
        tier="paid",
        place_id=place_id,
        custom_url="https://partner.example/viceroy?utm=now",
        show_badge=True,
        badge_label="Presented by",
    )
    decision = resolve_mention(
        city_conn, platform_conn, site_id=site_id, place_id=place_id, places_table=SYNTH_PLACES_TABLE
    )
    assert decision.tier == "paid"
    assert decision.href == "https://partner.example/viceroy?utm=now"
    assert decision.rel == "sponsored"
    assert decision.show_badge is True
    assert decision.badge_label == "Presented by"
    assert decision.resolved_via == "place"


def test_org_level_fallback_when_no_place_level_deal(city_conn, platform_conn, site_id):
    """A place with no partnership of its own inherits its org's paid
    deal -- 'every Marriott property' from the ticket's framing."""
    org_id = make_org(platform_conn, name="Marriott Group")
    make_partnership(platform_conn, site_id=site_id, tier="paid", org_id=org_id, custom_url="https://marriott.example")
    place_id = make_place(city_conn, org_id=org_id, slug="marriott-seminyak", name="Marriott Seminyak")

    decision = resolve_mention(
        city_conn, platform_conn, site_id=site_id, place_id=place_id, places_table=SYNTH_PLACES_TABLE
    )
    assert decision.tier == "paid"
    assert decision.org_id == org_id
    assert decision.resolved_via == "org"


def test_place_level_takes_precedence_over_org_level(city_conn, platform_conn, site_id):
    """Sec.11: 'active partnership (place-level, else org-level)' -- a
    place-specific deal must win even when the parent org also has one,
    otherwise a single independent property could never opt out of (or
    upgrade past) its group's blanket tier."""
    org_id = make_org(platform_conn, name="Some Group")
    make_partnership(platform_conn, site_id=site_id, tier="free", org_id=org_id)
    place_id = make_place(city_conn, org_id=org_id, slug="group-flagship", name="Group Flagship")
    make_partnership(
        platform_conn, site_id=site_id, tier="paid", place_id=place_id, custom_url="https://flagship.example"
    )

    decision = resolve_mention(
        city_conn, platform_conn, site_id=site_id, place_id=place_id, places_table=SYNTH_PLACES_TABLE
    )
    assert decision.tier == "paid"
    assert decision.resolved_via == "place"


def test_unknown_place_id_resolves_free(city_conn, platform_conn, site_id):
    decision = resolve_mention(
        city_conn, platform_conn, site_id=site_id, place_id="does-not-exist", places_table=SYNTH_PLACES_TABLE
    )
    assert decision.tier == "free"
    assert decision.resolved_via == "none"


def test_tie_break_prefers_most_recently_started_active_row(city_conn, platform_conn, site_id):
    """F62: the DB deliberately allows two simultaneously-'active'-status
    partnerships on the same (site, place) (e.g. queuing a renewal). This
    package resolves the tie by most recent starts_at."""
    place_id = make_place(city_conn, slug="renewal-case", name="Renewal Case")
    make_partnership(
        platform_conn,
        site_id=site_id,
        tier="listed",
        place_id=place_id,
        starts_at="2026-01-01T00:00:00Z",
    )
    make_partnership(
        platform_conn,
        site_id=site_id,
        tier="paid",
        place_id=place_id,
        custom_url="https://renewed.example",
        starts_at="2026-06-01T00:00:00Z",
    )
    decision = resolve_mention(
        city_conn, platform_conn, site_id=site_id, place_id=place_id, places_table=SYNTH_PLACES_TABLE
    )
    assert decision.tier == "paid"  # the later-starting row wins


def test_place_id_not_uuid_shaped_fails_closed_not_raises(city_conn, platform_conn, site_id):
    """Real Payload place ids are integers (`now_jakarta.public.places.id`
    is `serial integer`) but `engine.partnerships.place_id` is `uuid`
    (see resolver.py's module docstring). A non-uuid-shaped id must not
    raise 'invalid input syntax for type uuid' -- it should simply find
    no place-level partnership and fall through."""
    place_id = make_place(city_conn, place_id="42", slug="integer-id-place", name="Integer Id Place")
    # No exception, and no place-level match is possible for this id shape.
    decision = resolve_mention(
        city_conn, platform_conn, site_id=site_id, place_id=place_id, places_table=SYNTH_PLACES_TABLE
    )
    assert decision.tier == "free"
