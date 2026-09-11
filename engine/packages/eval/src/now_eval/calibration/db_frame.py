"""Builds the calibration sampling frame: one row per (city, article,
facet in {type, format}) carrying the classifier's already-written
proposal + confidence, joined against the article's own content.

Read-only, everywhere. Needs the `calibration` extra (sqlalchemy, psycopg,
now-db, now-platform-db) -- imported lazily by callers so the rest of
`now_eval` stays importable without it.

**Why read the DB instead of recomputing:** the task brief is explicit --
"Do not re-run classification." E2.1's `now-classifier classify` already
wrote every article's type/format decision (confidence included) to
`public.articles` / `engine.entity_terms` (accepted, confidence >= 0.85) or
`classification_reviews` (everything else, confidence < 0.85), and that
run must not race the F101 audit running in parallel. So this module
reconstructs, per article, exactly the (proposed_value, confidence) pair
`now_classifier.resolve.classify_article` produced, straight from what it
already persisted -- no classifier code is imported or re-run.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CITY_DB = {"jakarta": "now_jakarta", "bali": "now_bali"}


@dataclass(frozen=True)
class FacetOutcome:
    wp_id: int
    article_id: int
    facet: str                 # "type" | "format"
    proposed_value: str
    confidence: float
    outcome: str                # "accepted" | "review"


@dataclass(frozen=True)
class ArticleContent:
    wp_id: int
    title: str
    excerpt: str
    text_excerpt: str           # first ~800 chars of cleaned body -- enough for an LLM to judge type/format, small enough to keep prompts cheap
    categories: tuple[str, ...]  # kept for provenance/audit only -- NEVER shown to the blind LLM labeller


def _load_term_map(platform_engine) -> dict[str, str]:
    from sqlalchemy import text

    with platform_engine.connect() as conn:
        rows = conn.execute(
            text("select t.id::text, f.key from engine.terms t join engine.facets f on f.id = t.facet_id")
        ).fetchall()
    return {tid: fkey for tid, fkey in rows}


def load_term_slug_map(platform_engine) -> dict[str, tuple[str, str]]:
    """term_id -> (facet_key, slug). Needed for `location`, which -- unlike
    `type`/`format` -- is never written to `public.articles` as a plain
    column, so the accepted (auto-applied) value must be read back off
    `engine.entity_terms.term_id` via the platform vocabulary, not a
    convenience column."""
    from sqlalchemy import text

    with platform_engine.connect() as conn:
        rows = conn.execute(
            text(
                "select t.id::text, f.key, t.slug from engine.terms t "
                "join engine.facets f on f.id = t.facet_id"
            )
        ).fetchall()
    return {tid: (fkey, slug) for tid, fkey, slug in rows}


@dataclass(frozen=True)
class LocationOutcome:
    wp_id: int
    article_id: int
    proposed_value: str
    confidence: float
    source: str                # "ai" | "inferred" -- disambiguates the overloaded 0.90 value (see provenance.py)
    outcome: str                # "accepted" | "review"


def fetch_location_outcomes(city: str, term_slug_map: dict[str, tuple[str, str]]) -> list[LocationOutcome]:
    """`location` is multi-valued (rules.location, §4): unlike type/format,
    an article can legitimately carry several accepted-or-reviewed location
    rows at once, so this returns one `LocationOutcome` per row, not one per
    article."""
    from sqlalchemy import create_engine, text

    from now_db.settings import city_database_url

    engine = create_engine(city_database_url(CITY_DB[city]))
    out: list[LocationOutcome] = []
    with engine.connect() as conn:
        wp_by_id = {int(aid): int(wp) for aid, wp in conn.execute(
            text("select id, legacy_wp_id from public.articles where legacy_wp_id is not null")
        ).fetchall()}

        accepted_rows = conn.execute(
            text(
                """
                select entity_id::int as article_id, term_id::text as term_id, source, confidence
                from engine.entity_terms
                where entity_type = 'article'
                """
            )
        ).fetchall()
        for article_id, term_id, source, confidence in accepted_rows:
            facet_slug = term_slug_map.get(term_id)
            if facet_slug is None or facet_slug[0] != "location":
                continue
            wp_id = wp_by_id.get(article_id)
            if wp_id is None:
                continue
            out.append(LocationOutcome(wp_id=wp_id, article_id=article_id, proposed_value=facet_slug[1],
                                        confidence=float(confidence), source=source, outcome="accepted"))

        review_rows = conn.execute(
            text(
                """
                select rel.articles_id as article_id, cr.proposed_value, cr.source, cr.confidence
                from classification_reviews cr
                join classification_reviews_rels rel on rel.parent_id = cr.id and rel.path = 'entity'
                where cr.facet_key = 'location'
                """
            )
        ).fetchall()
        for article_id, proposed_value, source, confidence in review_rows:
            wp_id = wp_by_id.get(int(article_id))
            if wp_id is None:
                continue
            out.append(LocationOutcome(wp_id=wp_id, article_id=int(article_id), proposed_value=proposed_value,
                                        confidence=float(confidence), source=source, outcome="review"))
    return out


@dataclass(frozen=True)
class SubtypeOutcome:
    wp_id: int
    article_id: int
    proposed_value: str
    confidence: float
    source: str                # "ai" (per-article keyword match) | "inferred" (category-fixed or no-match fallback)
    outcome: str                # "accepted" | "review"


def fetch_subtype_outcomes(city: str, term_slug_map: dict[str, tuple[str, str]]) -> list[SubtypeOutcome]:
    """`subtype` is single-valued (one decision per article, same as type/
    format -- `now_classifier.db.write_results` writes exactly one row per
    article into either `engine.entity_terms` or `classification_reviews`,
    never both, same loop as type/format). It still needs its own fetcher
    rather than reusing `fetch_facet_outcomes`, though, because unlike type/
    format it has **no convenience column on `public.articles`** -- there is
    no `primary_subtype` -- so the accepted value must be read back off
    `engine.entity_terms.term_id` via the platform vocabulary, the same way
    `fetch_location_outcomes` does it. Same SQL shape as that function,
    parameterised for `facet_key = 'subtype'` instead of `'location'`."""
    from sqlalchemy import create_engine, text

    from now_db.settings import city_database_url

    engine = create_engine(city_database_url(CITY_DB[city]))
    out: list[SubtypeOutcome] = []
    with engine.connect() as conn:
        wp_by_id = {int(aid): int(wp) for aid, wp in conn.execute(
            text("select id, legacy_wp_id from public.articles where legacy_wp_id is not null")
        ).fetchall()}

        accepted_rows = conn.execute(
            text(
                """
                select entity_id::int as article_id, term_id::text as term_id, source, confidence
                from engine.entity_terms
                where entity_type = 'article'
                """
            )
        ).fetchall()
        for article_id, term_id, source, confidence in accepted_rows:
            facet_slug = term_slug_map.get(term_id)
            if facet_slug is None or facet_slug[0] != "subtype":
                continue
            wp_id = wp_by_id.get(article_id)
            if wp_id is None:
                continue
            out.append(SubtypeOutcome(wp_id=wp_id, article_id=article_id, proposed_value=facet_slug[1],
                                       confidence=float(confidence), source=source, outcome="accepted"))

        review_rows = conn.execute(
            text(
                """
                select rel.articles_id as article_id, cr.proposed_value, cr.source, cr.confidence
                from classification_reviews cr
                join classification_reviews_rels rel on rel.parent_id = cr.id and rel.path = 'entity'
                where cr.facet_key = 'subtype'
                """
            )
        ).fetchall()
        for article_id, proposed_value, source, confidence in review_rows:
            wp_id = wp_by_id.get(int(article_id))
            if wp_id is None:
                continue
            out.append(SubtypeOutcome(wp_id=wp_id, article_id=int(article_id), proposed_value=proposed_value,
                                       confidence=float(confidence), source=source, outcome="review"))
    return out


def fetch_facet_outcomes(city: str, term_map: dict[str, str]) -> list[FacetOutcome]:
    """Every type/format outcome already written for `city`, from both the
    accepted (`engine.entity_terms`) and reviewed (`classification_reviews`)
    sides -- together they are exhaustive over `public.articles` (E2.1's own
    write path guarantees every article gets exactly one outcome per facet,
    verified live: accepted+reviewed counts sum to the total article count in
    both cities)."""
    from sqlalchemy import text

    from now_db.settings import city_database_url
    from sqlalchemy import create_engine

    engine = create_engine(city_database_url(CITY_DB[city]))
    out: list[FacetOutcome] = []
    with engine.connect() as conn:
        id_by_wp = {int(wp): int(aid) for aid, wp in conn.execute(
            text("select id, legacy_wp_id from public.articles where legacy_wp_id is not null")
        ).fetchall()}
        wp_by_id = {aid: wp for wp, aid in id_by_wp.items()}

        accepted_rows = conn.execute(
            text(
                """
                select entity_id::int as article_id, term_id::text as term_id, confidence
                from engine.entity_terms
                where entity_type = 'article'
                """
            )
        ).fetchall()
        for article_id, term_id, confidence in accepted_rows:
            facet = term_map.get(term_id)
            if facet not in ("type", "format"):
                continue
            wp_id = wp_by_id.get(article_id)
            if wp_id is None:
                continue
            # proposed_value: re-derive the slug from public.articles.primary_type/format
            # rather than re-parsing the term slug here (single source of truth for
            # "what value did this article end up with").
            out.append(FacetOutcome(wp_id=wp_id, article_id=article_id, facet=facet,
                                     proposed_value="__accepted__", confidence=float(confidence), outcome="accepted"))

        review_rows = conn.execute(
            text(
                """
                select rel.articles_id as article_id, cr.facet_key, cr.proposed_value, cr.confidence
                from classification_reviews cr
                join classification_reviews_rels rel on rel.parent_id = cr.id and rel.path = 'entity'
                where cr.facet_key in ('type', 'format')
                """
            )
        ).fetchall()
        for article_id, facet, proposed_value, confidence in review_rows:
            wp_id = wp_by_id.get(int(article_id))
            if wp_id is None:
                continue
            out.append(FacetOutcome(wp_id=wp_id, article_id=int(article_id), facet=facet,
                                     proposed_value=proposed_value, confidence=float(confidence), outcome="review"))

        # Fill in the real accepted value from public.articles (primary_type / format enums).
        accepted_values = conn.execute(
            text("select id, primary_type::text, format::text from public.articles where id = any(:ids)"),
            {"ids": list({fo.article_id for fo in out if fo.outcome == "accepted"}) or [-1]},
        ).fetchall()
        value_by_article = {aid: {"type": t, "format": f} for aid, t, f in accepted_values}
        resolved: list[FacetOutcome] = []
        for fo in out:
            if fo.outcome == "accepted":
                real_value = value_by_article.get(fo.article_id, {}).get(fo.facet)
                if real_value is None:
                    continue  # shouldn't happen (accepted implies the column was set) -- skip defensively
                fo = FacetOutcome(wp_id=fo.wp_id, article_id=fo.article_id, facet=fo.facet,
                                   proposed_value=real_value, confidence=fo.confidence, outcome=fo.outcome)
            resolved.append(fo)
    return resolved


def load_article_content(city: str, root: Path) -> dict[int, ArticleContent]:
    """Reuses the E1.1/E2.1 loader (`now_taxonomy_evidence.sources`) rather
    than re-parsing `articles.jsonl` -- same HTML-cleaning, same excerpt
    convention the classifier itself was scored against."""
    from now_taxonomy_evidence.sources import load_articles

    out: dict[int, ArticleContent] = {}
    for a in load_articles(city, root):
        out[a.wp_id] = ArticleContent(
            wp_id=a.wp_id,
            title=a.title,
            excerpt=a.excerpt,
            text_excerpt=a.text[:800],
            categories=tuple(a.categories),
        )
    return out


def build_sampling_frame(city: str, root: Path, term_map: dict[str, str] | None = None) -> list[dict]:
    """One dict per (article, facet) outcome, content-joined. `term_map`
    can be passed in (shared across both cities) to avoid re-querying
    `now_platform` twice."""
    if term_map is None:
        from now_platform_db.settings import platform_database_url
        from sqlalchemy import create_engine

        term_map = _load_term_map(create_engine(platform_database_url()))

    outcomes = fetch_facet_outcomes(city, term_map)
    content = load_article_content(city, root)

    frame: list[dict] = []
    for fo in outcomes:
        c = content.get(fo.wp_id)
        if c is None:
            continue
        frame.append(
            {
                "key": f"{city}:{fo.wp_id}:{fo.facet}",
                "city": city,
                "wp_id": fo.wp_id,
                "article_id": fo.article_id,
                "facet": fo.facet,
                "proposed_value": fo.proposed_value,
                "confidence": fo.confidence,
                "outcome": fo.outcome,
                "title": c.title,
                "excerpt": c.excerpt,
                "text_excerpt": c.text_excerpt,
                "categories": list(c.categories),
            }
        )
    return frame
