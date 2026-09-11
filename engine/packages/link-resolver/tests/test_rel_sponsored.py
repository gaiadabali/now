"""Acceptance criterion: 'rel=\"sponsored\" cannot be omitted for paid' --
test the attempt, not just the happy path.

E1.5 measured 9,128/9,135 (99.9%) of the live archive's external links
carrying no `rel` at all. The fix has to survive someone *trying* to drop
it, not just never trying to set it -- so every test here is an attack:
try to construct or render a paid decision without `rel="sponsored"` and
show it is unreachable.
"""

from __future__ import annotations

import dataclasses

import pytest

from now_link_resolver.render import render_body_blocks
from now_link_resolver.types import LinkDecision


def test_rel_is_not_a_constructor_parameter_at_all():
    """There is no `rel=` keyword to pass in the first place."""
    sig_fields = {f.name for f in dataclasses.fields(LinkDecision)}
    assert "rel" not in sig_fields  # it's a computed @property, not a field


def test_paid_decision_rel_is_always_sponsored():
    decision = LinkDecision(
        tier="paid", place_id="p1", slug="p1", external_url="https://partner.example"
    )
    assert decision.rel == "sponsored"


def test_cannot_inject_a_different_rel_via_replace():
    """`dataclasses.replace` is the standard way to mutate a frozen
    dataclass -- confirm it has no `rel` field to overwrite, so even a
    caller who reaches for the general-purpose mutation tool cannot touch
    it. Attempting to pass `rel=` to `replace()` must fail loudly."""
    decision = LinkDecision(
        tier="paid", place_id="p1", slug="p1", external_url="https://partner.example"
    )
    with pytest.raises(TypeError):
        dataclasses.replace(decision, rel="nofollow")  # type: ignore[call-arg]
    # the original is untouched regardless
    assert decision.rel == "sponsored"


def test_non_paid_tiers_never_carry_rel_because_they_never_link():
    listed = LinkDecision(tier="listed", place_id="p1", slug="p1")
    free = LinkDecision(tier="free", place_id="p1")
    assert listed.rel is None
    assert free.rel is None


def test_rendered_paid_link_always_carries_rel_sponsored_regardless_of_other_fields():
    """Vary every other attribute (badge on/off, utm template present or
    not, arbitrary org_id strings) -- `rel="sponsored"` must appear in
    every case because the render path reads `decision.rel`, which cannot
    be anything else for tier='paid'."""
    variants = [
        LinkDecision(tier="paid", place_id="p1", slug="p1", external_url="https://a.example", show_badge=False),
        LinkDecision(
            tier="paid",
            place_id="p1",
            slug="p1",
            external_url="https://b.example",
            show_badge=True,
            badge_label="Ad",
            utm_template="utm_source=now",
            org_id="anything-at-all",
        ),
    ]
    blocks = [{"type": "paragraph", "html": '<span data-place="p1">Place</span>'}]
    for decision in variants:
        out = render_body_blocks(blocks, {"p1": decision})
        assert 'rel="sponsored"' in out[0]["html"]


def test_constructing_paid_decision_requires_a_real_url_not_silently_linkless():
    """A paid tier with no url would otherwise render an <a> with no
    href and no rel to speak of -- reject it at construction instead."""
    with pytest.raises(ValueError):
        LinkDecision(tier="paid", place_id="p1", slug="p1")  # no external_url
