"""Row 3 -- Similar (ARCHITECTURE.md Sec.7): "related reading" -- semantic
kNN over `engine.embeddings`, series-deduped, excluding the subject's own
L1 type.

**No embedder call, ever, on this path -- by construction, not by luck.**
`now_search.query_embedder.embed_query` turns *text* into a vector for
plain keyword search; Row 3 has no text query -- the "query" is the
subject article itself, which already has a stored vector in
`engine.embeddings` from E2.4's backfill. This module fetches that row
directly. The `fastembed` ONNX model (`query_embedder`'s ~46-100ms-p50
cost, see F53) is never loaded or invoked anywhere in this module. `p95 <
120ms` is only reachable at all because of this -- see the package
README's timing section.

Ordering follows Sec.8.G: the cheap, indexed hard filter
(status/self/competitor/quality/series-dedup, all pushed into SQL by
`now_filters.hard.build_articles_hard_filter_sql`) runs FIRST and produces
the eligible id set; the semantic ranking is then computed only over
exactly those ids, via `now_search.semantic.search_semantic(candidate_ids=...)`,
rather than fetching top-N by embedding and filtering afterward.

**F70 -- switched from this module's own `_restricted_semantic_knn` numpy
workaround to `now_search.semantic.search_semantic`'s restricted path, now
that F67 fixed it.** Until F67, `search_semantic`'s `candidate_ids`
restriction silently returned zero rows whenever the restriction was a
small fraction of `engine.embeddings` (HNSW visiting `ef_search`
approximate nodes *before* the filter applied) -- exactly Row 3's real
shape (a few hundred hard-filtered ids out of ~4,772). This module worked
around that with its own exact-cosine numpy computation over a batch
vector fetch, rather than serve wrong (silently empty) results from a
package it does not own. F67 fixed the root cause in `now_search` itself
(a `MATERIALIZED` CTE forces the restricted path to be exact -- see that
module's docstring) -- so the workaround is now redundant: `search_semantic
(candidate_ids=eligible_ids, limit=rerank_pool)` does the identical exact
cosine ranking, in SQL, over the identical restricted set. Kept only the
part that is a genuinely different job: `fast_similarity.py`'s
`FastEmbeddingSimilarity` still does pairwise candidate-to-candidate
similarity for MMR diversification (`.load()`, not `.from_preloaded()`
now -- there is no pre-fetched vector batch to hand it any more, so it
fetches its own, much smaller, final-pool-sized batch; see that module's
docstring). Side effect: this rail no longer fetches+parses ~400
`vector::text` rows in Python per request for ranking -- only the final
`rerank_pool` (~40) for MMR. Measured impact in this package's README.

Series dedup (Sec.8.A "one per series_key") is not reimplemented here --
`build_articles_hard_filter_sql(series_dedup=True)`'s own `DISTINCT ON`
already picks the highest-quality row per `series_key` group before this
module ever sees a candidate id, so a stale `[Updated 2024]` sibling of a
picked article can never even reach the semantic kNN restriction.
"""

from __future__ import annotations

from datetime import datetime

from now_blender.articles import fetch_article_meta
from now_blender.blend import compute_blend
from now_blender.components import BlendComponents
from now_blender.decay import describe_format_trust, freshness_component
from now_blender.mmr import diversify_ranked
from now_blender.platform import DEFAULT_SITE_RANKING_CONFIG, SiteRankingConfig
from now_blender.quality import fetch_quality
from now_blender.synthetic import deterministic_format
from now_filters.diversity import DiversityCaps
from now_filters.hard import (
    DEFAULT_ARTICLES_TABLE,
    ArticlesHardFilterQuery,
    build_articles_hard_filter_sql,
    fetch_articles_hard_filtered,
)
from now_filters.hidden_rival import hidden_rival_pattern_for_subject
from now_filters.ladder import run_ladder
from now_filters.models import Candidate, RungSpec
from now_filters.type_relations import TypeRelation
from now_quality.scoring import QUALITY_FLOOR
from now_search import query_embedder
from now_search.semantic import search_semantic
from sqlalchemy import text
from sqlalchemy.engine import Connection

from now_rails.display import fetch_article_titles
from now_rails.fast_similarity import FastEmbeddingSimilarity
from now_rails.ladders import ROW3_LADDER
from now_rails.models import ROW3, ComponentScoreOut, RailItem, RailResult
from now_rails.subject import ArticleSubject

DEFAULT_K = 6
DEFAULT_RERANK_POOL = 40  # ARCHITECTURE.md Sec.7: "re-ranked ... (top ~40)"

_SUBJECT_VEC_SQL = text(
    """
    SELECT vec::text AS vec_text
      FROM engine.embeddings
     WHERE entity_type = 'article' AND entity_id = :entity_id AND model = :model
    """
)


def _fetch_subject_vector(conn: Connection, article_id: int, model: str) -> list[float] | None:
    row = conn.execute(_SUBJECT_VEC_SQL, {"entity_id": str(article_id), "model": model}).first()
    if row is None:
        return None
    return [float(x) for x in row.vec_text.strip("[]").split(",")]


def _eligible_ids_fetch_fn(
    conn: Connection, subject: ArticleSubject, relations: dict[str, TypeRelation], *, articles_table: str
):
    # Computed once per request, not per rung: the pattern depends only on
    # the subject's own type + `engine.type_relations`, never on which
    # fallback rung is being tried -- and Sec.8.F is explicit that "the
    # competitor filter never relaxes at any rung", which this guard is
    # part of, so it must not become optional at a wider rung either.
    hidden_rival_pattern = hidden_rival_pattern_for_subject(subject.primary_type, relations)

    def _fetch(rung: RungSpec) -> list[Candidate]:
        # `rung.editorial_fallback` is repurposed here as "drop the
        # quality floor" -- see `ladders.py`'s module docstring.
        quality_floor = None if rung.editorial_fallback else QUALITY_FLOOR
        query: ArticlesHardFilterQuery = build_articles_hard_filter_sql(
            subject_type=subject.primary_type,
            relations=relations,
            exclude_self_id=subject.article_id,
            quality_floor=quality_floor,
            series_dedup=True,
            articles_table=articles_table,
            hidden_rival_pattern=hidden_rival_pattern,
        )
        return fetch_articles_hard_filtered(conn, query)

    return _fetch


def resolve_eligible_articles(
    conn: Connection,
    subject: ArticleSubject,
    relations: dict[str, TypeRelation],
    *,
    ladder: tuple[RungSpec, ...] = ROW3_LADDER,
    slots_needed: int = 400,
    articles_table: str = DEFAULT_ARTICLES_TABLE,
):
    """The SQL-hard-filter + fallback-ladder stage on its own -- status/
    self/competitor/quality-floor/series-dedup, all pushed into SQL, with
    `run_ladder`'s defensive re-check on top. Exposed as its own function
    (not inlined into `compute_row3`) specifically so a test can point
    `articles_table` at a `now_filters.synthetic` temp table and assert on
    competitor exclusion / series dedup **without needing embeddings for
    synthetic ids** -- `compute_row3` calls this exact function in
    production, so a test exercising it is exercising the real wiring, not
    a parallel reimplementation."""
    return run_ladder(
        _eligible_ids_fetch_fn(conn, subject, relations, articles_table=articles_table),
        subject_type=subject.primary_type,
        relations=relations,
        slots_needed=slots_needed,
        ladder=ladder,
    )


def compute_row3(
    conn: Connection,
    subject: ArticleSubject,
    relations: dict[str, TypeRelation],
    *,
    site_config: SiteRankingConfig = DEFAULT_SITE_RANKING_CONFIG,
    k: int = DEFAULT_K,
    rerank_pool: int = DEFAULT_RERANK_POOL,
    ladder: tuple[RungSpec, ...] = ROW3_LADDER,
    articles_table: str = DEFAULT_ARTICLES_TABLE,
    synthetic_format_overlay: bool = False,
    now: datetime | None = None,
) -> RailResult:
    model = query_embedder.model_name()
    subject_vec = _fetch_subject_vector(conn, subject.article_id, model)

    if subject_vec is None:
        # Should not happen post-E2.4 backfill (real data: 4,772/4,772
        # articles embedded, verified) -- handled, not assumed, exactly
        # like `now_blender.quality.fetch_quality`'s "missing key" stance.
        return RailResult(
            rail=ROW3,
            items=[],
            rung_name="no_subject_embedding",
            rung_index=-1,
            rungs_evaluated=[],
            pool_size=0,
            subject_type=subject.primary_type,
            weights_source=site_config.weights_source,
            unvalidated_reason=f"subject article {subject.article_id} has no {model} embedding row",
        )

    ladder_run = resolve_eligible_articles(
        conn,
        subject,
        relations,
        ladder=ladder,
        # Ask the SQL hard filter for a generous-but-bounded eligible-id
        # pool -- large enough that a real kNN ordering has something to
        # choose from rather than being capped by ladder truncation before
        # the vector search even runs. `rerank_pool * 3` (120 for the
        # default 40) is comfortably wider than the final display pool for
        # MMR/quality to have real choices.
        #
        # F70: pre-F67, this pool size also drove real p95 cost --
        # `_restricted_semantic_knn` (since removed) fetched every one of
        # these ids' vectors AS TEXT into Python to rank them itself,
        # measured at ~27ms at 400 ids vs. ~12ms at 100. Now that ranking
        # is `search_semantic(candidate_ids=...)`'s job (F67's fixed,
        # exact, SQL-side restricted kNN), `eligible_ids` here is only ever
        # passed to SQL as a plain `int[]` filter list -- no vector text
        # crosses into Python for this stage at all, so this pool's size no
        # longer has that cost attached to it.
        slots_needed=max(rerank_pool * 3, 100),
        articles_table=articles_table,
    )
    eligible_ids = [c.entity_id for c in ladder_run.result.candidates]

    unvalidated_reason: str | None = None
    if subject.primary_type is None:
        unvalidated_reason = (
            "subject article has no primary_type (F50 -- real archive-wide NULL); "
            "competitor exclusion cannot be computed from an unknown subject type, so "
            "this result is NOT proof the exclusion holds -- see synthetic overlay tests"
        )

    if not eligible_ids:
        return RailResult(
            rail=ROW3,
            items=[],
            rung_name=ladder_run.result.rung_name,
            rung_index=ladder_run.result.rung_index,
            rungs_evaluated=ladder_run.rungs_evaluated,
            pool_size=0,
            subject_type=subject.primary_type,
            weights_source=site_config.weights_source,
            unvalidated_reason=unvalidated_reason or "no eligible articles after hard filter + series dedup",
        )

    ranked_hits = search_semantic(
        conn, subject_vec, model=model, limit=rerank_pool, candidate_ids=eligible_ids
    )

    meta_by_id = fetch_article_meta(conn, [int(h.entity_id) for h in ranked_hits], site_config.format_term_ids)
    quality_by_id = fetch_quality(conn, [int(h.entity_id) for h in ranked_hits])

    candidates: list[Candidate] = []
    components_by_key: dict[tuple[str, int], list[ComponentScoreOut]] = {}
    relevance: dict[tuple[str, int], float] = {}
    for hit in ranked_hits:
        article_id = int(hit.entity_id)
        meta = meta_by_id.get(article_id)
        quality_row = quality_by_id.get(article_id)
        fmt = meta.format if meta is not None else None
        format_is_synthetic = False
        if fmt is None and synthetic_format_overlay:
            fmt = deterministic_format(article_id)
            format_is_synthetic = True
        candidate = Candidate(
            entity_type="article",
            entity_id=article_id,
            type=meta.primary_type if meta is not None else None,
            series_key=meta.series_key if meta is not None else None,
            format=fmt,
            published_at=meta.published_at if meta is not None else None,
        )
        candidates.append(candidate)

        semantic_sim = max(0.0, hit.raw_score)
        format_confidence = meta.format_confidence if meta is not None else None
        format_source = meta.format_source if meta is not None else None
        fresh = freshness_component(
            fmt, candidate.published_at, site_config.decay,
            format_confidence=format_confidence, format_source=format_source, now=now,
        )
        fresh_reason = describe_format_trust(fmt, format_confidence, format_source, site_config.decay)
        components = BlendComponents(
            semantic=semantic_sim,
            covis=None,
            freshness=fresh,
            quality=quality_row.score if quality_row is not None else None,
            geo=None,
            promo=None,
            freshness_explanation=fresh_reason,
        )
        blend = compute_blend(components, site_config.weights)
        relevance[candidate.key] = blend.normalized_score
        components_by_key[candidate.key] = [
            ComponentScoreOut(key=c.key, label=c.label, value=c.value, weight=c.weight, explanation=c.explanation, available=c.available)
            for c in blend.components
        ] + [
            ComponentScoreOut(
                key="format_is_synthetic", label="format_is_synthetic",
                value=1.0 if format_is_synthetic else 0.0, weight=0.0,
                explanation="1.0 if `format` was overlaid synthetically (F50) rather than real.",
                available=True,
            )
        ]

    # F70: `search_semantic` ranks in SQL and does not hand back vectors
    # (nor should it -- that's not its job), so there is nothing preloaded
    # to reuse here any more. `.load()` fetches exactly the vectors MMR
    # needs for pairwise candidate-to-candidate similarity: the FINAL
    # `rerank_pool`-sized set (~40), not the wider `eligible_ids` pool
    # (~120) `_restricted_semantic_knn` used to fetch to do its own
    # ranking -- see `fast_similarity.py`'s module docstring for why this
    # pairwise-similarity job is still this rail's own to do.
    sim_loader = FastEmbeddingSimilarity.load(conn, candidates, model=model)
    similarity_fn = sim_loader.similarity_fn()
    diversified = diversify_ranked(candidates, relevance, k=k, similarity_fn=similarity_fn, caps=DiversityCaps())

    display_ids = [c.entity_id for c in diversified]
    titles = fetch_article_titles(conn, display_ids)

    items = [
        RailItem(
            entity_type="article",
            entity_id=c.entity_id,
            rail=ROW3,
            position=rank,
            score=relevance[c.key],
            components=components_by_key[c.key],
            title=titles.get(c.entity_id, (None, None))[0],
            slug=titles.get(c.entity_id, (None, None))[1],
        )
        for rank, c in enumerate(diversified, start=1)
    ]

    return RailResult(
        rail=ROW3,
        items=items,
        rung_name=ladder_run.result.rung_name,
        rung_index=ladder_run.result.rung_index,
        rungs_evaluated=ladder_run.rungs_evaluated,
        pool_size=len(candidates),
        subject_type=subject.primary_type,
        weights_source=site_config.weights_source,
        unvalidated_reason=unvalidated_reason,
    )
