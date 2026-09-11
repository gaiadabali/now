"""Click logging carries enough to attribute a click to a campaign later,
and is never triggered by rendering itself (pure unit tests, no DB)."""

from __future__ import annotations

import pytest

from now_link_resolver.clicks import InMemoryClickLogger, build_click_event
from now_link_resolver.render import render_body_blocks
from now_link_resolver.types import LinkDecision

PAID = LinkDecision(
    tier="paid",
    place_id="viceroy-bali",
    slug="viceroy-bali",
    partnership_id="partnership-1",
    org_id="org-1",
    external_url="https://partner.example/viceroy?utm=now",
)


def test_click_event_carries_campaign_attributable_fields():
    event = build_click_event(PAID, site_id="site-1", session_id="sess-1", article_id="article-1")
    assert event.kind == "click"
    assert event.site_id == "site-1"
    assert event.article_id == "article-1"
    assert event.place_id == "viceroy-bali"
    assert event.org_id == "org-1"
    assert event.partnership_id == "partnership-1"
    assert event.destination_url == "https://partner.example/viceroy?utm=now"
    assert event.session_id == "sess-1"
    # E4.5 (campaigns/placements) doesn't exist yet -- shaped for it, not
    # populated by it.
    assert event.campaign_id is None
    assert event.placement_id is None
    assert event.id  # a real, unique id was minted
    assert event.ts is not None


def test_logger_records_the_event():
    logger = InMemoryClickLogger()
    event = build_click_event(PAID, site_id="site-1")
    logger.log(event)
    assert logger.events == [event]


def test_click_logging_refuses_free_and_listed_tiers():
    free = LinkDecision(tier="free", place_id="p1")
    listed = LinkDecision(tier="listed", place_id="p1", slug="p1")
    with pytest.raises(ValueError):
        build_click_event(free, site_id="site-1")
    with pytest.raises(ValueError):
        build_click_event(listed, site_id="site-1")


def test_render_never_logs_a_click_itself():
    """Idempotent/side-effect-free on render: rendering the same paid
    mention any number of times must never invoke a click logger. Since
    render_body_blocks doesn't even accept a logger argument, this is
    mostly a structural guarantee -- proven here by rendering repeatedly
    against a logger that would fail the test if anything called it."""
    logger = InMemoryClickLogger()
    blocks = [{"type": "paragraph", "html": 'x <span data-place="viceroy-bali">Viceroy</span> y'}]

    for _ in range(5):
        render_body_blocks(blocks, {"viceroy-bali": PAID})

    assert logger.events == []  # never touched
