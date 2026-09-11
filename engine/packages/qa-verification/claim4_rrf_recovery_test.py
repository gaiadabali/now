"""QA test of E3.3/F58's diagnosis: "the headline nDCG drop (0.7642 -> 0.375)
is mechanically explained by Sec.7 having no lexical/RRF term, not a bug."

Method: duplicate BlenderReranker's re-ranking loop (read-only use of
now_blender/now_search internals -- no product code is modified) but add
back an RRF-derived term to the blend, min-max normalized per-query over
the candidate pool, weighted comparably to the semantic term. If the
diagnosis is right, restoring this term should pull the headline nDCG@10
back up toward the pre-blend baseline (0.7642), because the query's own
source article -- which the eval's grade-3 relevance entry always is --
is exactly the kind of near-exact lexical/title match RRF ranks first and
a pure semantic+quality blend can lose.

Does not modify now_blender, now_search, or now_filters. Writes nothing
to the DB (log_features left off).
"""

from __future__ import annotations

from dataclasses import dataclass

from now_blender.articles import fetch_article_meta
from now_blender.components import BlendComponents
from now_blender.connections import city_engine
from now_blender.covisitation import fetch_covis_scores
from now_blender.decay import freshness_component
from now_blender.mmr import diversify_ranked
from now_blender.platform import DEFAULT_SITE_RANKING_CONFIG
from now_blender.quality import fetch_quality
from now_blender.similarity import build_similarity_fn
from now_filters.models import Candidate
from now_filters.type_relations import load_type_relations
from now_search import query_embedder
from now_search.engine import SearchEngine

from now_eval.datasets.search_queries import build_provisional_query_set
from now_eval.datasets.sources import load_articles
from now_eval.metrics.ndcg import mean_ndcg_at_k

K = 10
RERANK_POOL = max(K * 5, 100)
W_RRF = 0.35  # comparable magnitude to w_sem (0.35) per ARCHITECTURE.md Sec.7 stage 2


def _to_candidate(article_id, meta, quality_row):
    return Candidate(
        entity_type="article",
        entity_id=article_id,
        type=meta.primary_type if meta is not None else None,
        series_key=meta.series_key if meta is not None else None,
        format=meta.format if meta is not None else None,
        quality_score=quality_row.score if quality_row is not None else None,
        published_at=meta.published_at if meta is not None else None,
    )


def rank_with_rrf_term(engine, conn, config, bridge, query: str, candidate_ids, k: int):
    search_result = engine.search(query, k=RERANK_POOL, compute_facets=False)
    fused_hits = search_result.hits
    if not fused_hits:
        return []

    article_ids = [int(h.entity_id) for h in fused_hits]
    meta_by_id = fetch_article_meta(conn, article_ids)
    quality_by_id = fetch_quality(conn, article_ids)
    covis_by_id = fetch_covis_scores(conn, subject_entity_id=None, candidate_entity_ids=[])

    # min-max normalize rrf_score over this query's candidate pool -> [0,1]
    rrf_scores = [h.rrf_score for h in fused_hits]
    lo, hi = min(rrf_scores), max(rrf_scores)
    span = (hi - lo) or 1.0

    candidates = []
    fused_by_key = {}
    relevance = {}
    for hit in fused_hits:
        article_id = int(hit.entity_id)
        meta = meta_by_id.get(article_id)
        quality_row = quality_by_id.get(article_id)
        candidate = _to_candidate(article_id, meta, quality_row)
        candidates.append(candidate)
        fused_by_key[candidate.key] = hit

        semantic = max(0.0, hit.semantic_raw_score) if hit.semantic_raw_score is not None else None
        fresh = freshness_component(candidate.format, candidate.published_at, config.decay, now=None)
        rrf_norm = (hit.rrf_score - lo) / span

        # Stage 2 per corrected ARCHITECTURE.md Sec.7: w_rrf*fused + old blend terms.
        # Reuse compute_blend's own renormalize-over-available-terms semantics by
        # hand here (adds one more named term to the same pattern).
        named = [
            ("rrf", rrf_norm, W_RRF),
            ("semantic", semantic, config.weights.w_sem),
            ("covis", covis_by_id.get(str(article_id)), config.weights.w_cf),
            ("freshness", fresh, config.weights.w_fresh),
            ("quality", quality_row.score if quality_row is not None else None, config.weights.w_qual),
            ("geo", None, config.weights.w_geo),
            ("promo", None, config.weights.w_promo),
        ]
        raw = 0.0
        wsum = 0.0
        for _, value, weight in named:
            if value is not None:
                raw += weight * value
                wsum += weight
        relevance[candidate.key] = (raw / wsum) if wsum > 0 else 0.0

    similarity_fn, _ = build_similarity_fn(conn, candidates, model=query_embedder.model_name())
    diversified = diversify_ranked(candidates, relevance, k=k, similarity_fn=similarity_fn, lambda_=0.7)

    candidate_set = set(candidate_ids)
    out = []
    for candidate in diversified:
        wp_id = bridge.db_to_wp.get(candidate.entity_id)
        if wp_id is None:
            continue
        wp_ref = f"wp:{wp_id}"
        if wp_ref in candidate_set:
            out.append(wp_ref)
        if len(out) >= k:
            break
    return out


@dataclass
class WpIdBridge:
    db_to_wp: dict


def load_bridge(conn):
    from sqlalchemy import text
    rows = conn.execute(text("SELECT id, legacy_wp_id FROM public.articles WHERE legacy_wp_id IS NOT NULL")).fetchall()
    return WpIdBridge(db_to_wp={db_id: int(wp_id) for db_id, wp_id in rows})


def main():
    queries = build_provisional_query_set()
    all_articles = load_articles()
    all_article_ids = [a.article_id for a in all_articles]

    eng = city_engine("now_jakarta")
    conn = eng.connect()
    try:
        search_engine = SearchEngine(conn)
        search_engine.warm_up()
        config = DEFAULT_SITE_RANKING_CONFIG
        bridge = load_bridge(conn)

        rankings = []
        relevances_full = []
        relevances_no_source = []

        for q in queries:
            ranking = rank_with_rrf_term(search_engine, conn, config, bridge, q.query, list(all_article_ids), K)
            rankings.append(ranking)
            rel_map = q.relevance_map()
            relevances_full.append(rel_map)
            relevances_no_source.append({aid: grade for aid, grade in rel_map.items() if grade < 3.0})

        full_value = mean_ndcg_at_k(rankings, relevances_full, K)
        no_source_value = mean_ndcg_at_k(rankings, relevances_no_source, K)

        print(f"n queries: {len(queries)}")
        print(f"W_RRF used: {W_RRF}")
        print(f"nDCG@10 WITH rrf term restored (source incl.):  {full_value:.6f}   (no-rrf blend: 0.375108, pre-blend baseline: 0.764200)")
        print(f"nDCG@10 WITH rrf term restored (source excl.):  {no_source_value:.6f}   (no-rrf blend: 0.065276)")
    finally:
        search_engine.close()
        conn.close()


if __name__ == "__main__":
    main()
