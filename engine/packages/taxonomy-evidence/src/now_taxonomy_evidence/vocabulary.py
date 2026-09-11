"""Corpus-derived vocabulary check, both directions.

1. Every seed term (label + aliases) is counted as *distinct articles
   mentioning it* per city, over title + body. Zero across 9,201 articles
   -> removal candidate; < 5 -> "rare" (kept visible, not recommended for
   removal -- the classifier may still need the value as an output).
2. Every candidate term from `lexicons.py` that is NOT already in the seed
   is counted the same way; the frequent ones are addition candidates.
3. The editor-authored `post_tag` vocabulary (terms.jsonl) is listed where
   no seed term covers the tag -- the editors' own words for what they
   publish are the most honest corpus vocabulary we have.

Mention counts are lexical: "party" as a vibe and "party" as in "third
party" are the same token. Numbers are indicative; the report says so.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .lexicons import CANDIDATES
from .sources import Article

# seed labels that are not lexical (facet values that never appear as words)
_SKIP_LABELS = {"$", "$$", "$$$", "$$$$", "Other", "Elsewhere in Indonesia", "Indonesia", "International", "Unknown", "Eat", "Stay", "Do", "Drink", "Shop", "Event", "Editorial", "Wellness"}
_MIN_LEN = 3


def _forms(label: str, aliases: list[str]) -> list[str]:
    out = []
    for s in [label, *aliases]:
        s = re.sub(r"\s*\(.*?\)", "", s or "").strip()
        if len(s) >= _MIN_LEN and s not in _SKIP_LABELS:
            out.append(s)
    return out


class _Matcher:
    """One alternation regex; longest surface form wins; a match counts for
    every term that owns that surface form (e.g. `subtype/spa` and
    `amenities/spa` both claim "spa")."""

    def __init__(self, forms_by_key: dict[str, list[str]]):
        self.owners: dict[str, list[str]] = {}
        for key, forms in forms_by_key.items():
            for f in forms:
                self.owners.setdefault(f.lower(), []).append(key)
        alts = sorted(self.owners, key=len, reverse=True)
        self.re = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(a) for a in alts) + r")(?![\w-])", re.I) if alts else None

    def keys_in(self, text: str) -> set[str]:
        if not self.re:
            return set()
        out: set[str] = set()
        for m in self.re.finditer(text):
            out.update(self.owners[m.group(0).lower()])
        return out


def analyse_vocabulary(articles_by_city: dict[str, list[Article]], seed: dict, tags_by_city: dict[str, dict[str, int]]) -> dict:
    cities = list(articles_by_city)
    # ---- seed terms ---------------------------------------------------------
    seed_forms: dict[str, list[str]] = {}
    seed_meta: dict[str, dict] = {}
    for facet, terms in seed["terms"].items():
        if facet in ("type", "format", "price_band"):
            continue
        for t in terms:
            key = f"{facet}/{t['slug']}"
            forms = _forms(t["label"], t.get("aliases") or [])
            if facet == "location" and t["slug"] in ("indonesia", "other", "international"):
                forms = []
            if not forms:
                continue
            seed_forms[key] = forms
            seed_meta[key] = {"facet": facet, "slug": t["slug"], "label": t["label"], "proposed": t.get("proposed", False), "parent": t.get("parent"), "forms": forms}
    seed_m = _Matcher(seed_forms)
    seed_hits: dict[str, Counter] = {k: Counter() for k in seed_forms}
    seed_title_hits: dict[str, Counter] = {k: Counter() for k in seed_forms}

    # ---- candidates (not already covered by a seed surface form) ----------
    covered = {f.lower() for forms in seed_forms.values() for f in forms}
    seed_labels = {(m["facet"], m["label"].lower()) for m in seed_meta.values()} | {(m["facet"], m["slug"].lower()) for m in seed_meta.values()}
    facet_family = {"location_jakarta": "location", "location_bali": "location", "location_elsewhere": "location", "location_international": "location", "venue_kind": "subtype"}
    cand_forms: dict[str, list[str]] = {}
    cand_meta: dict[str, dict] = {}
    for facet, entries in CANDIDATES.items():
        for label, forms in entries.items():
            fs = [f for f in forms if f.lower() not in covered and len(f) >= _MIN_LEN]
            if not fs:
                continue
            key = f"{facet}/{label}"
            fam = facet_family.get(facet, facet)
            # a candidate whose label IS a seed term is not a missing term -- its
            # uncovered surface forms are alias suggestions for that seed term
            is_alias = (fam, label.lower()) in seed_labels
            cand_forms[key] = fs
            cand_meta[key] = {"facet": facet, "label": label, "forms": fs, "alias_of_seed": is_alias}
    cand_m = _Matcher(cand_forms)
    cand_hits: dict[str, Counter] = {k: Counter() for k in cand_forms}
    cand_title_hits: dict[str, Counter] = {k: Counter() for k in cand_forms}

    for city, arts in articles_by_city.items():
        for a in arts:
            body = f"{a.title} {a.excerpt} {a.text}"
            for k in seed_m.keys_in(body):
                seed_hits[k][city] += 1
            for k in seed_m.keys_in(a.title):
                seed_title_hits[k][city] += 1
            for k in cand_m.keys_in(body):
                cand_hits[k][city] += 1
            for k in cand_m.keys_in(a.title):
                cand_title_hits[k][city] += 1

    seed_rows = []
    for k, meta in seed_meta.items():
        row = dict(meta)
        row["key"] = k
        row["hits"] = {c: seed_hits[k].get(c, 0) for c in cities}
        row["title_hits"] = {c: seed_title_hits[k].get(c, 0) for c in cities}
        row["total"] = sum(row["hits"].values())
        seed_rows.append(row)
    seed_rows.sort(key=lambda r: (r["facet"], -r["total"]))

    cand_rows = []
    for k, meta in cand_meta.items():
        row = dict(meta)
        row["key"] = k
        row["hits"] = {c: cand_hits[k].get(c, 0) for c in cities}
        row["title_hits"] = {c: cand_title_hits[k].get(c, 0) for c in cities}
        row["total"] = sum(row["hits"].values())
        cand_rows.append(row)
    cand_rows.sort(key=lambda r: (r["facet"], -r["total"]))

    # ---- tags not covered by any seed form ---------------------------------
    tags_uncovered: dict[str, list[dict]] = {}
    for city, tags in tags_by_city.items():
        rows = []
        for name, count in sorted(tags.items(), key=lambda kv: -kv[1]):
            if count < 5 or not name:
                continue
            if seed_m.keys_in(name):
                continue
            rows.append({"tag": name, "count": count})
        tags_uncovered[city] = rows[:60]

    total_articles = sum(len(v) for v in articles_by_city.values())
    return {
        "method": "distinct articles whose title+body contain the term or one of its aliases (case-insensitive, word-boundary); lexical, so homonyms inflate a few counts (party, solo, classic, business, casual); title-only counts are the stricter signal",
        "_all_candidates": cand_rows,
        "articles_scanned": {c: len(v) for c, v in articles_by_city.items()},
        "seed_terms": seed_rows,
        "seed_unused": [r for r in seed_rows if r["total"] == 0],
        "seed_rare": [r for r in seed_rows if 0 < r["total"] < 5],
        "candidates": [r for r in cand_rows if r["total"] >= 12 and not r["alias_of_seed"]],
        "alias_suggestions": [r for r in cand_rows if r["total"] >= 12 and r["alias_of_seed"]],
        "candidate_threshold": 12,
        "tags_uncovered": tags_uncovered,
        "total_articles": total_articles,
    }
