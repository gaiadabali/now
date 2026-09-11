"""F38-comparable measurement for this package's blend + MMR re-ranker,
mirroring `engine/packages/qa-verification/scripts/
e31_ndcg_source_excluded.py` (read-only, not edited -- QA-owned) exactly:
each eval query's own source article contributes a grade-3 relevance
entry ("find the document this phrase came from"); this script also
reports nDCG@10 with that entry removed, leaving only the grade-1 peer
documents, so the blend's number is comparable to E3.1's own
0.7642-headline / 0.0684-honest pair on the same, apples-to-apples
basis.

Does not modify now_eval or now_search/now_filters; reimplements the
same few lines of harness glue QA.3's script does, against
`BlenderEvalSUT` instead of `SearchEvalSUT`. `synthetic_format_overlay`
stays False throughout (see `now_blender.eval_sut`'s docstring) -- this
is the real-data-only number.
"""

from __future__ import annotations

from now_blender.connections import city_engine
from now_blender.eval_sut import BlenderEvalSUT
from now_eval.datasets.search_queries import build_provisional_query_set
from now_eval.datasets.sources import load_articles
from now_eval.metrics.ndcg import mean_ndcg_at_k

K = 10


def main() -> None:
    queries = build_provisional_query_set()
    all_articles = load_articles()
    all_article_ids = [a.article_id for a in all_articles]

    engine = city_engine("now_jakarta")
    conn = engine.connect()
    try:
        sut = BlenderEvalSUT.build(conn, log_features=False)

        rankings = []
        relevances_full = []
        relevances_no_source = []
        n_source_was_only_relevant = 0

        for q in queries:
            ranking = sut.rank(q.query, list(all_article_ids), K)
            rankings.append(ranking)
            rel_map = q.relevance_map()
            relevances_full.append(rel_map)

            no_source = {aid: grade for aid, grade in rel_map.items() if grade < 3.0}
            relevances_no_source.append(no_source)
            if not no_source:
                n_source_was_only_relevant += 1

        full_value = mean_ndcg_at_k(rankings, relevances_full, K)
        no_source_value = mean_ndcg_at_k(rankings, relevances_no_source, K)

        print(f"n queries:                            {len(queries)}")
        print(f"queries with NO peer (grade-1) docs:  {n_source_was_only_relevant}")
        print(f"nDCG@10 as reported (source incl.):    {full_value:.6f}   (E3.1 comparable: 0.764200)")
        print(f"nDCG@10 source excluded (peers only):  {no_source_value:.6f}   (E3.1 comparable: 0.068200 / QA.3-recomputed 0.0684)")
        print(f"delta:                                {full_value - no_source_value:+.6f}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
