"""Pure unit tests for render.py -- no DB needed. Proves the three-tier
ladder renders correctly and that rendering is idempotent/side-effect-free."""

from __future__ import annotations

import copy

from now_link_resolver.render import render_body_blocks
from now_link_resolver.types import LinkDecision

BODY_BLOCKS = [
    {"type": "heading", "level": 2, "text": "Where to stay"},
    {
        "type": "paragraph",
        "html": 'We stayed at <span data-place="viceroy-bali">The Viceroy Bali</span> for three nights.',
    },
    {
        "type": "list",
        "ordered": False,
        "items": ['Nearby: <span data-place="warung-mia">Warung Mia</span> for lunch.'],
    },
]


def _decisions_for(tier: str) -> dict[str, LinkDecision]:
    if tier == "free":
        return {"viceroy-bali": LinkDecision(tier="free", place_id="viceroy-bali", slug="viceroy-bali")}
    if tier == "listed":
        return {"viceroy-bali": LinkDecision(tier="listed", place_id="viceroy-bali", slug="viceroy-bali")}
    if tier == "paid":
        return {
            "viceroy-bali": LinkDecision(
                tier="paid",
                place_id="viceroy-bali",
                slug="viceroy-bali",
                partnership_id="p-1",
                org_id="org-1",
                external_url="https://partner.example/viceroy?utm=now",
                show_badge=True,
                badge_label="Presented by",
            )
        }
    raise ValueError(tier)


def test_free_tier_renders_plain_text():
    out = render_body_blocks(BODY_BLOCKS, _decisions_for("free"))
    html = out[1]["html"]
    assert "<a " not in html
    assert "The Viceroy Bali" in html
    assert "data-place" not in html


def test_listed_tier_renders_internal_link():
    out = render_body_blocks(BODY_BLOCKS, _decisions_for("listed"))
    html = out[1]["html"]
    assert '<a href="/places/viceroy-bali">The Viceroy Bali</a>' in html
    assert "rel=" not in html


def test_paid_tier_renders_external_link_with_badge_and_attribution():
    out = render_body_blocks(BODY_BLOCKS, _decisions_for("paid"))
    html = out[1]["html"]
    assert 'href="https://partner.example/viceroy?utm=now"' in html
    assert 'rel="sponsored"' in html
    assert 'data-partner="org-1"' in html
    assert 'data-partnership="p-1"' in html
    assert 'badge--partner' in html
    assert "Presented by" in html


def test_renders_inside_list_items_too():
    decisions = {"warung-mia": LinkDecision(tier="listed", place_id="warung-mia", slug="warung-mia")}
    out = render_body_blocks(BODY_BLOCKS, decisions)
    item = out[2]["items"][0]
    assert '<a href="/places/warung-mia">Warung Mia</a>' in item


def test_unresolved_mention_falls_back_to_plain_text():
    out = render_body_blocks(BODY_BLOCKS, {})  # no decision supplied at all
    html = out[1]["html"]
    assert "<a " not in html
    assert "The Viceroy Bali" in html


def test_render_does_not_mutate_input_blocks():
    original = copy.deepcopy(BODY_BLOCKS)
    render_body_blocks(BODY_BLOCKS, _decisions_for("paid"))
    assert BODY_BLOCKS == original


def test_render_is_idempotent_same_inputs_same_output():
    decisions = _decisions_for("paid")
    first = render_body_blocks(BODY_BLOCKS, decisions)
    second = render_body_blocks(BODY_BLOCKS, decisions)
    assert first == second

    third = render_body_blocks(first, decisions)  # re-rendering already-rendered blocks
    # no `data-place` markers remain, so a second pass is a strict no-op
    assert third == first
