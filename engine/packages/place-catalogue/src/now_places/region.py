"""Out-of-region detection by name (and address/area when present).

Sec.1.1: "Jakarta's table holds Bali: 301 Jakarta rows carry a Bali area
name". Sec.9.3 step 2: such a row is KEPT (Jakarta stories genuinely
mention it) with `region_ok = false`, and is never an itinerary candidate
for Jakarta. `region_ok` is properly a coordinate test (P1.3 writes it once
a row is geocoded); until then every row has `region_ok = false` by
default and this module is the only signal there is -- so triage FLAGS
these rows for review and never moves or junks them.

The location tree is the same seed `now_geocode` matches against
(`engine/packages/taxonomy/seed/terms/location.json`); its matcher and its
stopword handling are reused rather than re-implemented.

A row is flagged only when it names a place OUTSIDE the site's region and
nothing INSIDE it ("The Oberoi Lombok" names Lombok and, through the
Seminyak alias "Oberoi", Bali -- a mixed signal stays unflagged).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from now_geocode.terms import LocationTree, load_location_tree
from now_geocode.textnorm import normalize_name

# The site slug is also the slug of its region's root node in the tree.
SITE_REGION_ROOT = {"bali": "bali", "jakarta": "jakarta"}


@dataclass(frozen=True)
class RegionVerdict:
    out_of_region: bool
    region: str | None = None  # the top-level region the name points at
    matched: str | None = None  # the tree node's label that matched


@lru_cache(maxsize=1)
def _tree() -> LocationTree:
    return load_location_tree()


def _region_of(tree: LocationTree, slug: str) -> str:
    """The node just below the tree roots ("jakarta", "bali", "other"'s
    children collapse to "other"), or the root itself for "international"."""
    chain = [slug]
    node = tree.nodes.get(slug)
    while node is not None and node.parent_slug is not None:
        chain.append(node.parent_slug)
        node = tree.nodes.get(node.parent_slug)
    # chain ends at a root ("indonesia" or "international")
    root = chain[-1]
    if root == "international":
        return "international"
    if len(chain) >= 2:
        top = chain[-2]
        return top if top in SITE_REGION_ROOT else "other"
    return root


def _all_matches(tree: LocationTree, text: str) -> list[str]:
    hay = normalize_name(text)
    if not hay:
        return []
    found: list[str] = []
    for needle, slug, depth in tree._match_index:  # noqa: SLF001 -- same index now_geocode uses
        if depth == 0:
            # The roots ("Indonesia", "International") are words in half
            # the archive's names and say nothing about which city.
            continue
        if not needle or len(needle) < 4:
            # 3-letter aliases ("PIM", "MKG", "GBK", "CGK") are far more
            # often something else inside a venue name.
            continue
        if re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", hay):
            found.append(slug)
    return found


def region_verdict(site: str, name: str, address: str | None = None, area_term: str | None = None) -> RegionVerdict:
    tree = _tree()
    home = SITE_REGION_ROOT[site]
    slugs = _all_matches(tree, " ".join(t for t in (name, address or "") if t))
    if area_term and area_term in tree.nodes:
        slugs.append(area_term)
    if not slugs:
        return RegionVerdict(False)
    regions = {s: _region_of(tree, s) for s in slugs}
    if any(r == home for r in regions.values()):
        return RegionVerdict(False, home)
    # Deepest (most specific) outside match names the region in the report.
    slug = max(slugs, key=lambda s: tree.nodes[s].depth)
    return RegionVerdict(True, regions[slug], tree.label_of(slug))
