"""QA.3 claim 1: quantify how much of E3.1's nDCG@10=0.7642 comes from
the eval query set's self-referential construction (F38's concern).

Each query in `build_provisional_query_set()` is derived from an
article's own title/focus_keyword, and that SAME article is graded
relevance=3 in its own query's relevant set ("find the document this
phrase came from"). This script recomputes nDCG@10 with the source
article's grade-3 entry REMOVED from each query's relevance map --
leaving only the grade-1 same-category peers -- so we can see what the
number looks like when the trivial "phrase came from this doc" signal
is not rewarded.

This does not modify now_eval or now_search; it reimplements the two
lines of harness glue locally against the same SearchEngine/SUT.
"""
from __future__ import annotations

from now_search.connections import city_engine
from now_eval.datasets.search_queries import build_provisional_query_set
from now_eval.datasets.sources import load_articles
from now_eval.metrics.ndcg import mean_ndcg_at_k

from now_search.eval_sut import SearchEvalSUT

K = 10


def main() -> None:
    queries = build_provisional_query_set()
    all_articles = load_articles()
    all_article_ids = [a.article_id for a in all_articles]

    engine = city_engine("now_jakarta")
    conn = engine.connect()
    try:
        sut = SearchEvalSUT.build(conn)

        rankings = []
        relevances_full = []
        relevances_no_source = []
        n_source_was_only_relevant = 0

        for q in queries:
            ranking = sut.rank(q.query, list(all_article_ids), K)
            rankings.append(ranking)
            rel_map = q.relevance_map()
            relevances_full.append(rel_map)

            # The query's own source article is the one entry graded 3.0.
            no_source = {aid: grade for aid, grade in rel_map.items() if grade < 3.0}
            relevances_no_source.append(no_source)
            if not no_source:
                n_source_was_only_relevant += 1

        full_value = mean_ndcg_at_k(rankings, relevances_full, K)
        no_source_value = mean_ndcg_at_k(rankings, relevances_no_source, K)

        print(f"n queries:                         {len(queries)}")
        print(f"queries with NO peer (grade-1) docs: {n_source_was_only_relevant}  "
              f"(nDCG contribution for these becomes 0.0 once source is excluded)")
        print(f"nDCG@10 as reported (source incl.):  {full_value:.6f}")
        print(f"nDCG@10 source excluded (peers only): {no_source_value:.6f}")
        print(f"delta:                               {full_value - no_source_value:+.6f}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
