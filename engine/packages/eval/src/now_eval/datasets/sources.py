"""Loaders for the two upstream source files this package treats as
read-only ground truth. Neither file is owned by this package — both
come from E1.1/E1.4 (jakarta/, outside engine/packages/eval/) — so
these are loaders, not generators.

Path resolution: callers may pass an explicit path; otherwise these walk
up from the current working directory looking for ARCHITECTURE.md to
find the repo root, then resolve the well-known relative path. This
keeps `now-eval build-datasets` runnable both from the repo root (local
dev) and from a CI job that checks out the whole monorepo without a
hardcoded absolute path.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

ARTICLES_RELATIVE_PATH = "jakarta/content/extracted/articles.jsonl"
TAXONOMY_MAPPING_RELATIVE_PATH = "jakarta/site/taxonomy-mapping.json"


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "ARCHITECTURE.md").is_file():
            return candidate
    raise FileNotFoundError(
        "could not locate repo root (no ARCHITECTURE.md found walking up from "
        f"{current}) -- pass an explicit path instead of relying on auto-discovery"
    )


def default_articles_path() -> Path:
    return find_repo_root() / ARTICLES_RELATIVE_PATH


def default_taxonomy_mapping_path() -> Path:
    return find_repo_root() / TAXONOMY_MAPPING_RELATIVE_PATH


@dataclass(frozen=True)
class Article:
    wp_id: int
    slug: str
    title: str
    status: str
    categories: tuple[str, ...]
    focus_keyword: str | None
    metadesc: str | None
    primary_category_id: int | None

    @property
    def article_id(self) -> str:
        # Stable, human-legible id used across every labelled set in
        # this package. Deliberately not the raw wp_id (int) so it
        # reads unambiguously in JSONL fixtures and can't be confused
        # with a term id or a price.
        return f"wp:{self.wp_id}"


def _parse_article(raw: dict[str, Any]) -> Article:
    meta = raw.get("meta") or {}
    focus = meta.get("_yoast_wpseo_focuskw")
    focus = focus.strip() if isinstance(focus, str) and focus.strip() else None
    metadesc = meta.get("_yoast_wpseo_metadesc")
    metadesc = metadesc.strip() if isinstance(metadesc, str) and metadesc.strip() else None
    primary_raw = meta.get("_yoast_wpseo_primary_category")
    primary_id: int | None = None
    if primary_raw is not None and str(primary_raw).strip():
        try:
            primary_id = int(primary_raw)
        except (TypeError, ValueError):
            primary_id = None
    return Article(
        wp_id=raw["wp_id"],
        slug=raw.get("slug", ""),
        title=raw.get("title", ""),
        status=raw.get("status", ""),
        categories=tuple(raw.get("categories") or ()),
        focus_keyword=focus,
        metadesc=metadesc,
        primary_category_id=primary_id,
    )


def iter_articles(path: Path | None = None) -> Iterator[Article]:
    path = path or default_articles_path()
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield _parse_article(json.loads(line))


def load_articles(path: Path | None = None) -> list[Article]:
    return list(iter_articles(path))


@dataclass(frozen=True)
class CategoryPrior:
    wp_term_id: int
    name: str
    slug: str
    is_print_issue: bool
    confidence: str
    type_: str | None
    per_article_dims: tuple[str, ...]

    @property
    def type_is_category_certain(self) -> bool:
        """True when `type_` applies to every article in this category
        (not flagged 'per_article' in taxonomy-mapping.json) at HIGH
        confidence -- the bar this package uses for the type-label
        proxy set. See PROVENANCE.md for why this bar, not a lower one."""
        return (
            not self.is_print_issue
            and self.confidence == "high"
            and self.type_ is not None
            and "type" not in self.per_article_dims
        )


def load_category_priors(path: Path | None = None) -> dict[str, CategoryPrior]:
    """name -> CategoryPrior. Keyed by name (not wp_term_id) because
    articles.jsonl's `categories` field carries the WP category display
    name, not the term id -- matching on `_yoast_wpseo_primary_category`
    (a term id) is done separately in related.py."""
    path = path or default_taxonomy_mapping_path()
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    out: dict[str, CategoryPrior] = {}
    for raw in doc["categories"]:
        prior = raw.get("prior") or {}
        out[raw["name"]] = CategoryPrior(
            wp_term_id=raw["wp_term_id"],
            name=raw["name"],
            slug=raw["slug"],
            is_print_issue=bool(raw.get("is_print_issue")),
            confidence=raw.get("confidence", ""),
            type_=prior.get("type"),
            per_article_dims=tuple(raw.get("per_article") or ()),
        )
    return out


def load_category_priors_by_term_id(path: Path | None = None) -> dict[int, CategoryPrior]:
    by_name = load_category_priors(path)
    return {c.wp_term_id: c for c in by_name.values()}
