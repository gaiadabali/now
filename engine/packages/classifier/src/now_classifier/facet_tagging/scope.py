"""Which facets are even eligible on which articles.

Spec (WS5 ticket): "cuisine only on eat/drink articles; price_band only on
venue types; the others [topic, audience, vibe, occasion] on all." A
scope-excluded (facet, article) pair is never scored, never sampled for
calibration, and never written -- not merely down-weighted -- so an
`unknown`-typed article can never accidentally pick up a `price_band` tag
just because some lexical cue fired.

`VENUE_TYPES` is imported, not re-typed, from `now_taxonomy_evidence.text`
(the same constant the existing type/format cue instrument already uses to
mark `exclude_same` venue types in `type_relations.json`) -- one
definition of "what counts as a venue" for the whole codebase.
"""
from __future__ import annotations

from now_taxonomy_evidence.text import VENUE_TYPES

CUISINE_TYPES = frozenset({"eat", "drink"})
PRICE_BAND_TYPES = frozenset(VENUE_TYPES)  # stay, eat, drink, wellness, shop

# Facets with no scope restriction: eligible regardless of primary_type
# (including an article whose type is still unresolved/None) -- topic and
# audience tag the SUBJECT of a piece, not a venue, so an editorial op-ed
# about expat life is exactly as eligible as a hotel review; vibe/occasion
# describe a reader's mood/moment, which any article can evoke.
UNSCOPED_FACETS = frozenset({"topic", "audience", "vibe", "occasion"})

SCOPED_FACETS = frozenset({"cuisine", "price_band"})

ALL_FACETS = UNSCOPED_FACETS | SCOPED_FACETS


def in_scope(facet_key: str, primary_type: str | None) -> bool:
    if facet_key == "cuisine":
        return primary_type in CUISINE_TYPES
    if facet_key == "price_band":
        return primary_type in PRICE_BAND_TYPES
    if facet_key in UNSCOPED_FACETS:
        return True
    raise ValueError(f"unknown facet_key for WS5 tagging: {facet_key!r}")
