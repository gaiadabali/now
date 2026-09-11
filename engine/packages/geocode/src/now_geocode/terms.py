"""Loads the seeded location tree (`engine/packages/taxonomy/seed/terms/location.json`,
the same file E1.4 seeded into `now_platform.engine.terms` and that
`now_jakarta.public.places.area_term` is an enum over) and provides the
two lookups the area-term fallback (ARCHITECTURE.md §8/§15) needs:

- `match_text`: does a piece of free text (address / venue name / city)
  name a location-tree node, by slug/label/alias — most-specific match
  wins.
- `nearest`: given a resolved lat/lng, which node's seeded centroid is
  closest (haversine), for when text matching finds nothing but a real
  coordinate exists.

This module never talks to Postgres — it reads the taxonomy package's
JSON seed file directly, so `now-geocode` has no dependency on `now-db`
or a live database for its core (file-in, file-out) path. The DB is
only touched by the optional `postgis-demo` command (see `pgdemo.py`).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from now_geocode.textnorm import normalize_name

# ARCHITECTURE.md §15 / E1.4: 85 terms, Jakarta + Bali to neighbourhood,
# rooted at "indonesia" plus a proposed "international" leaf.
DEFAULT_LOCATION_SEED = (
    Path(__file__).resolve().parents[3] / "taxonomy" / "seed" / "terms" / "location.json"
)

# A handful of the seed's aliases are, in isolation, common Indonesian or
# English dictionary words rather than distinctive place names: "batu"
# (stone), "kota" (city), "bukit" (hill), "tim" (team, also a common
# English first name), "solo" (English "by oneself"). Matching these as
# free-text substrings produces real false positives — caught on the
# actual corpus: a Bali venue at "Jl. Pantai Batu Belig" (Kuta Utara,
# Badung) was assigned area_term=malang (East Java, ~700km away) purely
# because "Batu" is also an alias for Malang's Batu district. Dropped
# from the match index entirely; the affected nodes keep their other,
# non-generic aliases (Malang still matches on "Bromo", Cikini still
# matches on "Taman Ismail Marzuki", etc). This is a known blunt
# instrument, not a general word-sense-disambiguation fix — worth
# revisiting if/when E2.3's venue-name-in-prose extraction needs the
# same lookup against much noisier free text.
_GENERIC_ALIAS_STOPWORDS = {"batu", "kota", "bukit", "tim", "solo"}


@dataclass
class TermNode:
    slug: str
    label: str
    depth: int  # 0 = root
    parent_slug: str | None
    aliases: tuple[str, ...] = ()
    geo: tuple[float, float] | None = None  # (lat, lng)

    @property
    def match_strings(self) -> tuple[str, ...]:
        return tuple({normalize_name(self.label), *[normalize_name(a) for a in self.aliases]} - {""})


@dataclass
class LocationTree:
    nodes: dict[str, TermNode] = field(default_factory=dict)  # slug -> node
    # (normalized string, slug, depth) — sorted deepest-node-first after
    # finalize() so "Kemang" (depth 3) wins over "South Jakarta" (depth 2)
    # even though the latter is a longer string; length is only the
    # tiebreak *within* the same depth.
    _match_index: list[tuple[str, str, int]] = field(default_factory=list)

    def add(self, node: TermNode) -> None:
        self.nodes[node.slug] = node
        for s in node.match_strings:
            if s in _GENERIC_ALIAS_STOPWORDS:
                continue
            self._match_index.append((s, node.slug, node.depth))
        # slug itself is always matchable, hyphens read as spaces
        slug_text = normalize_name(node.slug.replace("-", " "))
        if slug_text not in _GENERIC_ALIAS_STOPWORDS:
            self._match_index.append((slug_text, node.slug, node.depth))

    def finalize(self) -> None:
        self._match_index.sort(key=lambda triple: (-triple[2], -len(triple[0])))

    def match_text(self, *texts: str | None) -> str | None:
        """Most-specific (deepest node in the tree, longest string as a
        tiebreak) node whose label/alias/slug appears as a whole word in
        any of `texts`. Returns a slug or None."""

        haystacks = [normalize_name(t) for t in texts if t]
        for needle, slug, _depth in self._match_index:
            if not needle or len(needle) < 3:
                continue  # too short to match safely ("do", "at"...)
            pattern = r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])"
            for hay in haystacks:
                if re.search(pattern, hay):
                    return slug
        return None

    def nearest(self, lat: float, lng: float, *, max_km: float = 60.0) -> tuple[str, float] | None:
        """Nearest node with a seeded centroid, within `max_km`. Returns
        (slug, distance_km) or None. Only leaf-ish precision matters for
        Row 2's radius fallback, but any node with a geo is eligible —
        a nearer district beats a farther neighbourhood."""

        best: tuple[str, float] | None = None
        for node in self.nodes.values():
            if node.geo is None:
                continue
            d = _haversine_km(lat, lng, node.geo[0], node.geo[1])
            if best is None or d < best[1]:
                best = (node.slug, d)
        if best and best[1] <= max_km:
            return best
        return None

    def label_of(self, slug: str) -> str:
        node = self.nodes.get(slug)
        return node.label if node else slug


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_location_tree(path: Path | None = None) -> LocationTree:
    path = path or DEFAULT_LOCATION_SEED
    data = json.loads(path.read_text(encoding="utf-8"))
    tree = LocationTree()

    def walk(terms: list[dict], parent_slug: str | None, depth: int) -> None:
        for t in terms:
            geo = None
            if t.get("geo"):
                geo = (t["geo"]["lat"], t["geo"]["lng"])
            node = TermNode(
                slug=t["slug"],
                label=t["label"],
                depth=depth,
                parent_slug=parent_slug,
                aliases=tuple(t.get("aliases", [])),
                geo=geo,
            )
            tree.add(node)
            if t.get("children"):
                walk(t["children"], t["slug"], depth + 1)

    walk(data["terms"], None, 0)
    tree.finalize()
    return tree
