"""Read-only loaders for everything the evidence pack consumes.

Nothing here is owned by this package -- articles come from the E1.1/E1.9
extractors, category metadata from the E1.x REST harvest, the Jakarta prior
from E1.4, the vocabulary from `engine/packages/taxonomy/seed`. All of it is
read, none of it is written.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .text import clean_html

CITIES = ("jakarta", "bali")

# The site's own node in the §4 location tree (interim convention from the
# taxonomy README: `sites.slug == terms.slug`).
HOME_LOCATION = {"jakarta": "jakarta", "bali": "bali"}

BODY_CHARS = 6000  # enough for cue scoring and the text proxy; keeps memory flat


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "ARCHITECTURE.md").is_file():
            return candidate
    raise FileNotFoundError("could not locate the repo root (no ARCHITECTURE.md above %s)" % current)


@dataclass
class Article:
    city: str
    wp_id: int
    title: str
    slug: str
    date: str
    categories: list[str]
    primary_category_id: int | None
    excerpt: str
    text: str
    focus_kw: str | None
    views: int | None

    @property
    def year(self) -> int:
        return int(self.date[:4]) if self.date else 0


@dataclass
class Category:
    city: str
    name: str
    slug: str
    term_id: int | None
    parent_id: int | None
    parent_name: str | None
    description: str
    wp_count: int | None          # WP's own count (all statuses, from the REST harvest)
    published: int = 0            # distinct published articles carrying the category
    years: dict[int, int] = field(default_factory=dict)
    yoast_primary: int = 0        # articles whose Yoast primary category is this one

    @property
    def first_year(self) -> int | None:
        return min(self.years) if self.years else None

    @property
    def last_year(self) -> int | None:
        return max(self.years) if self.years else None


def _norm_name(name: str) -> str:
    return html.unescape(name or "").replace(" ", " ").strip()


def iter_articles(city: str, root: Path | None = None) -> Iterator[Article]:
    root = root or find_repo_root()
    path = root / city / "content" / "extracted" / "articles.jsonl"
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            if raw.get("type") not in (None, "post") or raw.get("status") not in (None, "publish"):
                continue
            meta = raw.get("meta") or {}
            prim = meta.get("_yoast_wpseo_primary_category")
            try:
                prim_id = int(prim) if prim not in (None, "") else None
            except (TypeError, ValueError):
                prim_id = None
            focus = meta.get("_yoast_wpseo_focuskw")
            focus = focus.strip() if isinstance(focus, str) and focus.strip() else None
            views = meta.get("wpb_post_views_count")
            try:
                views_i = int(views) if views not in (None, "") else None
            except (TypeError, ValueError):
                views_i = None
            yield Article(
                city=city,
                wp_id=int(raw["wp_id"]),
                title=_norm_name(raw.get("title") or ""),
                slug=raw.get("slug") or "",
                date=raw.get("date") or "",
                categories=[_norm_name(c) for c in (raw.get("categories") or [])],
                primary_category_id=prim_id,
                excerpt=clean_html(raw.get("excerpt") or "")[:600],
                text=clean_html(raw.get("content_html") or "")[:BODY_CHARS],
                focus_kw=focus,
                views=views_i,
            )


def load_articles(city: str, root: Path | None = None) -> list[Article]:
    return list(iter_articles(city, root))


def load_categories(city: str, articles: list[Article], root: Path | None = None) -> dict[str, Category]:
    """Category registry keyed by decoded display name.

    Primary source is the REST harvest (`content/harvested/categories.jsonl`)
    because it carries term ids, parents and editor-written descriptions;
    `content/extracted/terms.jsonl` is the fallback (Bali's WXR carries no
    term ids). Published counts are always recomputed from the articles --
    WP's `count` includes drafts and other post types.
    """
    root = root or find_repo_root()
    rows: list[dict[str, Any]] = []
    harvested = root / city / "content" / "harvested" / "categories.jsonl"
    extracted = root / city / "content" / "extracted" / "terms.jsonl"
    if harvested.is_file():
        with open(harvested, encoding="utf-8") as fh:
            rows = [json.loads(l, strict=False) for l in fh if l.strip()]
    elif extracted.is_file():
        with open(extracted, encoding="utf-8") as fh:
            rows = [r for r in (json.loads(l, strict=False) for l in fh if l.strip()) if r.get("taxonomy") == "category"]
    by_id = {r.get("term_id"): r for r in rows if r.get("term_id") is not None}
    cats: dict[str, Category] = {}
    for r in rows:
        name = _norm_name(r.get("name") or "")
        parent = r.get("parent")
        parent_name = _norm_name(by_id[parent]["name"]) if parent in by_id else None
        cats[name] = Category(
            city=city,
            name=name,
            slug=r.get("slug") or "",
            term_id=r.get("term_id"),
            parent_id=parent if parent not in (0, None) else None,
            parent_name=parent_name if parent not in (0, None) else None,
            description=re.sub(r"\s+", " ", clean_html(r.get("description") or "")).strip(),
            wp_count=r.get("count"),
        )
    # anything the articles carry that the registry lacks
    for a in articles:
        for c in a.categories:
            if c not in cats:
                cats[c] = Category(city=city, name=c, slug=re.sub(r"[^a-z0-9]+", "-", c.lower()).strip("-"),
                                   term_id=None, parent_id=None, parent_name=None, description="", wp_count=None)
    for a in articles:
        for c in set(a.categories):
            cat = cats[c]
            cat.published += 1
            cat.years[a.year] = cat.years.get(a.year, 0) + 1
        if a.primary_category_id is not None:
            for cat in cats.values():
                if cat.term_id == a.primary_category_id:
                    cat.yoast_primary += 1
                    break
    return cats


def load_tags(city: str, root: Path | None = None) -> dict[str, int]:
    """Editor-authored `post_tag` vocabulary with WP counts (terms.jsonl)."""
    root = root or find_repo_root()
    path = root / city / "content" / "extracted" / "terms.jsonl"
    out: dict[str, int] = {}
    if not path.is_file():
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            t = json.loads(line, strict=False)
            if t.get("taxonomy") == "post_tag":
                out[_norm_name(t.get("name") or "")] = int(t.get("count") or 0)
    return out


def load_e14_mapping(root: Path | None = None) -> dict[str, dict[str, Any]]:
    """E1.4's Jakarta draft, keyed by decoded category name. Read-only."""
    root = root or find_repo_root()
    path = root / "jakarta" / "site" / "taxonomy-mapping.json"
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    return {_norm_name(c["name"]): c for c in doc["categories"]}


def load_seed(root: Path | None = None) -> dict[str, Any]:
    """The seed vocabulary as a flat structure: facet -> list of term dicts
    (slug, label, aliases, parent, proposed, path)."""
    root = root or find_repo_root()
    seed_dir = root / "engine" / "packages" / "taxonomy" / "seed"
    facets = json.load(open(seed_dir / "facets.json", encoding="utf-8"))["facets"]
    out: dict[str, list[dict[str, Any]]] = {f["key"]: [] for f in facets}

    def walk(facet: str, terms: list[dict[str, Any]], parent: str | None, path: list[str], child_facet: str | None):
        for t in terms:
            entry = {
                "slug": t["slug"], "label": t.get("label", t["slug"]), "aliases": list(t.get("aliases") or []),
                "parent": parent, "proposed": bool(t.get("proposed")), "path": path + [t["slug"]],
                "from_spec": bool(t.get("from_spec")), "notes": t.get("notes") or t.get("description") or "",
            }
            out.setdefault(facet, []).append(entry)
            kids = t.get("children") or []
            if kids:
                walk(child_facet or facet, kids, t["slug"], path + [t["slug"]], child_facet if child_facet != facet else None)

    for f in facets:
        p = seed_dir / "terms" / f"{f['key']}.json"
        if not p.is_file():
            continue
        doc = json.load(open(p, encoding="utf-8"))
        child_facet = doc.get("children_facet")
        walk(f["key"], doc["terms"], None, [], child_facet)
    return {"facets": facets, "terms": out, "seed_dir": str(seed_dir)}
