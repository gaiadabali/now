"""Alias-based literal matching for the five facets whose vocabulary IS
mostly lexical (topic, audience, vibe, cuisine, occasion) -- `price_band`
has no aliases at all (its labels are "$".."$$$$") and gets its own
hand-authored cue set in `price_cues.py`.

Deliberately the same shape as `now_taxonomy_evidence.text.
build_location_matcher`/`match_locations` (word-boundary literal match on
label + aliases, title vs. lead vs. body zones) -- reused conceptually,
not re-derived, because that instrument's whole design point ("a name in
the headline is a stronger, more deliberate editorial signal than one
buried in paragraph six") applies just as much to a topic or a cuisine
term as it does to a place name. Not literally reused as code because
location's matcher has two things this one must NOT have: the
`geo_scope=abroad` recursive-tree walk (topic/audience/vibe/cuisine/
occasion are flat, no parent/child) and the Indonesian-dish-noun
suppression (for cuisine specifically, a dish NAME appearing next to a
place word is exactly the signal wanted, not noise to suppress).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ZONE_TITLE = "title"
ZONE_LEAD = "lead"     # dek/excerpt + body[:400], matching the cue instrument's LEAD_W zone
ZONE_BODY = "body"     # body[400:1600]

_ZONE_RANK = {ZONE_TITLE: 3, ZONE_LEAD: 2, ZONE_BODY: 1}

LEAD_CHARS = 400
BODY_CHARS = 1600


@dataclass(frozen=True)
class TermPattern:
    slug: str
    pattern: re.Pattern[str]


def build_term_matcher(
    seed_terms: list[dict],
    facet_key: str | None = None,
    alias_exclusions: dict[tuple[str, str], "frozenset[str] | str"] | None = None,
) -> list[TermPattern]:
    """`seed_terms`: the flat per-facet list `now_taxonomy_evidence.sources.
    load_seed()["terms"][facet_key]` already produces (slug/label/aliases).
    One compiled alternation per term (label + aliases), not one pattern
    per alias, so a term with many short aliases can't win by sheer alias
    count against a term with one strong one -- `match_term_zones` below
    only asks "did ANY of this term's names appear", not how many times.

    `alias_exclusions` is `calibration.ALIAS_EXCLUSIONS` (passed explicitly
    rather than imported here, so this module stays measurement-agnostic
    and testable on its own): a term whose exclusion value is `"*"` is
    dropped ENTIRELY (its label included -- the label itself is the
    problem, e.g. `audience`'s "local"); otherwise the named aliases are
    dropped but the label and remaining aliases still match."""
    out: list[TermPattern] = []
    exclusions = alias_exclusions or {}
    for t in seed_terms:
        key = (facet_key, t["slug"])
        excluded = exclusions.get(key)
        if excluded == "*":
            continue
        drop = {a.lower() for a in excluded} if excluded else set()
        names = [t["label"], *[a for a in (t.get("aliases") or [])]]
        cleaned = sorted(
            {re.sub(r"\s*\(.*?\)", "", n).strip() for n in names
             if n and len(n.strip()) >= 3 and n.strip().lower() not in drop},
            key=len, reverse=True,
        )
        if not cleaned:
            continue
        alt = "|".join(re.escape(n) for n in cleaned)
        pat = re.compile(r"(?<![\w-])(?:" + alt + r")(?![\w-])", re.I)
        out.append(TermPattern(slug=t["slug"], pattern=pat))
    return out


def match_term_zones(title: str, dek_excerpt: str, body: str, matcher: list[TermPattern]) -> dict[str, str]:
    """Returns {slug: strongest_zone} for every term that matched anywhere.
    `dek_excerpt` is folded into the lead zone alongside body[:400] (both
    are "the reader's first ~2 sentences", the same trust level as location's
    lead zone); `body` is expected pre-sliced to BODY_CHARS by the caller
    (this function does not re-slice, so callers control the exact budget
    once, matching `now_taxonomy_evidence.text`'s own convention)."""
    lead = f"{dek_excerpt} || {body[:LEAD_CHARS]}"
    rest = body[LEAD_CHARS:BODY_CHARS]
    out: dict[str, str] = {}
    for tp in matcher:
        zone = None
        if tp.pattern.search(title):
            zone = ZONE_TITLE
        elif tp.pattern.search(lead):
            zone = ZONE_LEAD
        elif tp.pattern.search(rest):
            zone = ZONE_BODY
        if zone:
            out[tp.slug] = zone
    return out


def zone_rank(zone: str) -> int:
    return _ZONE_RANK[zone]
