"""Orchestrates one Inspector page render: runs the generators, fuses
them, joins quality/freshness/filter-trace/fallback-rung per candidate,
and hands the template a single `InspectReport`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.engine import Connection

from now_blender.decay import DecayPolicy, FALLBACK_DECAY_POLICY
from now_blender.format_terms_cache import load_format_term_ids_cached

from now_inspector import filters_adapter, filters_trace, generators
from now_inspector.articles import fetch_article, fetch_articles, fetch_quality_bulk
from now_inspector.blender import illustrative_blend
from now_inspector.diversity import DiversityStub, stub as diversity_stub
from now_inspector.freshness import classify as classify_freshness
from now_inspector.models import ArticleRow, CandidateTrace, GeneratorPanel


def _resolve_format_trust_context(
    platform_conn: Connection | None, site_slug: str | None
) -> tuple[frozenset[str], DecayPolicy]:
    """F124/F125 (T2): resolves the format-facet term id set (for the
    entity_terms join) and the site's real decay policy (for
    `min_format_confidence`), or the package fallback (0.85) when no
    platform connection was given -- an internal debug tool run without
    `--platform-url` still works, it just cannot resolve any format
    term's trust and reports every classified format as untrusted
    (fails closed, same stance as `now_blender.platform
    .DEFAULT_SITE_RANKING_CONFIG`), which is disclosed via
    `FreshnessResult.withheld_reason` rather than silently skipped."""
    if platform_conn is None:
        return frozenset(), FALLBACK_DECAY_POLICY
    format_term_ids = load_format_term_ids_cached(
        platform_conn, cache_key=platform_conn.engine.url.database or "default"
    )
    decay_policy = FALLBACK_DECAY_POLICY
    if site_slug is not None:
        from now_blender.platform import load_site_ranking_config

        decay_policy = load_site_ranking_config(platform_conn, site_slug).decay
    return format_term_ids, decay_policy


@dataclass(frozen=True)
class InspectReport:
    mode: str  # "query" | "article_id"
    query: str | None
    article_id: int | None
    seed_article: ArticleRow | None
    seed_not_found: bool
    generator_panels: list[GeneratorPanel]
    candidates: list[CandidateTrace]
    diversity: DiversityStub
    filters_status: filters_adapter.FiltersPackageStatus
    error: str | None = None


def build_query_report(
    conn: Connection, query: str, *, limit: int = 15, platform_conn: Connection | None = None, site_slug: str | None = None
) -> InspectReport:
    raw = generators.run_query_mode(conn, query, limit=25)
    fused = generators.fuse(raw)[:limit]
    return _assemble(
        conn, mode="query", query=query, article_id=None, raw=raw, fused=fused,
        platform_conn=platform_conn, site_slug=site_slug,
    )


def build_article_report(
    conn: Connection, article_id: int, *, limit: int = 15, platform_conn: Connection | None = None, site_slug: str | None = None
) -> InspectReport:
    format_term_ids, _decay_policy = _resolve_format_trust_context(platform_conn, site_slug)
    seed = fetch_article(conn, article_id, format_term_ids)
    if seed is None:
        return InspectReport(
            mode="article_id",
            query=None,
            article_id=article_id,
            seed_article=None,
            seed_not_found=True,
            generator_panels=[],
            candidates=[],
            diversity=diversity_stub(),
            filters_status=filters_adapter.probe(),
            error=f"No article with id={article_id} in public.articles.",
        )
    raw = generators.run_article_id_mode(conn, article_id, limit=25)
    fused = generators.fuse(raw)[:limit]
    return _assemble(
        conn, mode="article_id", query=None, article_id=article_id, raw=raw, fused=fused, seed=seed,
        platform_conn=platform_conn, site_slug=site_slug,
    )


def _assemble(
    conn: Connection,
    *,
    mode: str,
    query: str | None,
    article_id: int | None,
    raw: generators.RawGenerators,
    fused,
    seed: ArticleRow | None = None,
    platform_conn: Connection | None = None,
    site_slug: str | None = None,
) -> InspectReport:
    format_term_ids, decay_policy = _resolve_format_trust_context(platform_conn, site_slug)
    entity_ids = [h.entity_id for h in fused]
    numeric_ids = [int(e) for e in entity_ids]

    # Fetch titles for the FULL raw generator output too (panel 1 shows up
    # to `limit` raw hits per rail, which is wider than the fused top-k) --
    # otherwise anything past the fused cutoff renders as "?" even though
    # the row is real, just not in the fused top-k shown in panel 2/3.
    raw_ids = {int(h.entity_id) for h in raw.lexical_hits} | {int(h.entity_id) for h in raw.semantic_hits}
    title_lookup_ids = sorted(raw_ids | set(numeric_ids))

    article_map = fetch_articles(conn, numeric_ids, format_term_ids)
    title_map = fetch_articles(conn, title_lookup_ids, format_term_ids) if raw_ids - set(numeric_ids) else article_map
    if seed is not None:
        article_map[seed.id] = seed
        title_map[seed.id] = seed
    quality_map = fetch_quality_bulk(conn, entity_ids)
    fallback_map = filters_adapter.get_fallback_rungs(entity_ids)

    titles = {aid: a.title for aid, a in title_map.items()}
    panels = generators.to_panels(raw, titles)

    candidates: list[CandidateTrace] = []
    for hit in fused:
        eid_int = int(hit.entity_id)
        article = article_map.get(eid_int)
        quality = quality_map.get(hit.entity_id)
        freshness = classify_freshness(
            article.format if article else None,
            article.published_at if article else None,
            format_confidence=article.format_confidence if article else None,
            format_source=article.format_source if article else None,
            trust_policy=decay_policy,
        )

        trace = filters_trace.build_trace(
            article=article,
            entity_id=hit.entity_id,
            quality=quality,
            seed_article=seed,
            seed_article_id=article_id,
        )
        ok, reason = filters_trace.survived(trace)

        blend = illustrative_blend(
            semantic_raw_score=hit.semantic_raw_score,
            rrf_score=hit.rrf_score,
            quality_score=quality.score if quality else None,
            freshness_component=freshness.decay_component,
        )

        candidates.append(
            CandidateTrace(
                article=article,
                entity_id=hit.entity_id,
                lexical_rank=hit.lexical_rank,
                lexical_raw_score=hit.lexical_raw_score,
                semantic_rank=hit.semantic_rank,
                semantic_raw_score=hit.semantic_raw_score,
                rrf_score=hit.rrf_score,
                quality=quality,
                freshness=freshness,
                blended_score=blend.illustrative_score,
                blend_components=blend.components,
                filter_trace=trace,
                survived=ok,
                survival_reason=reason,
            )
        )

    return InspectReport(
        mode=mode,
        query=query,
        article_id=article_id,
        seed_article=seed,
        seed_not_found=False,
        generator_panels=panels,
        candidates=candidates,
        diversity=diversity_stub(),
        filters_status=filters_adapter.probe(),
    )
