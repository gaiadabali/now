"""Normalized Discounted Cumulative Gain.

This is the single highest-consequence piece of code in this package: a
subtly wrong nDCG silently invalidates every future search-ranking
comparison. The implementation follows the standard graded-relevance
formulation exactly as given on Wikipedia's "Discounted cumulative gain"
article (the exponential-gain variant, which is the one nearly every IR
paper and library — trec_eval, sklearn, TensorFlow Ranking — means by
"nDCG" unless stated otherwise):

    DCG@k  = sum_{i=1}^{k} (2^rel_i - 1) / log2(i + 1)      (i is 1-indexed rank)
    IDCG@k = DCG@k of the same relevance multiset in ideal (sorted-desc) order
    nDCG@k = DCG@k / IDCG@k                                  (0 if IDCG@k == 0)

`tests/test_ndcg.py` reproduces the worked example from that article by
hand (relevances 3,2,3,0,1,2) plus binary-relevance and edge cases, so a
future change to this file that breaks the formula fails loudly rather
than silently.

CAUTION — do not "correct" this code against Wikipedia's *displayed*
numbers. The article's own figures (DCG6=6.861, IDCG6=8.740,
nDCG6=0.785) come from the LINEAR-gain formula, and its IDCG is built
from an ideal list extended with two documents (D7 rel=3, D8 rel=2) that
sit outside the 6-item ranked list. This module deliberately implements
the EXPONENTIAL-gain variant and computes IDCG by re-sorting only the
same query's judged relevances -- the practical convention used by
trec_eval and sklearn, and the only one available here since the harness
has no separate pool of unretrieved-but-relevant documents.

Under this formula and convention the worked example gives
    nDCG@6 = 0.9488107485678985
which is what `test_ndcg.py` asserts. (An earlier version of this
docstring quoted 0.9608; that figure is 6.861/7.141 -- the linear-gain
result under a same-set IDCG -- and matches neither this code nor the
article. Verified by hand-recomputation against the article's raw
wikitext during the QA.2 audit.)
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence


def dcg_at_k(relevances: Sequence[float], k: int) -> float:
    """DCG@k for a sequence of relevance grades already in ranked order
    (relevances[0] is rank 1, the top result).

    Grades beyond position k are ignored. A shorter sequence than k is
    fine — missing positions simply contribute 0 gain, exactly as if a
    non-relevant document had filled the slot.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    total = 0.0
    for i, rel in enumerate(relevances[:k]):
        rank = i + 1
        total += (2**rel - 1) / math.log2(rank + 1)
    return total


def ndcg_at_k(
    ranked_ids: Sequence[str],
    relevance: Mapping[str, float],
    k: int,
) -> float:
    """Normalized DCG@k for a system's ranked output against graded
    relevance judgments.

    Args:
        ranked_ids: the system-under-test's output, best result first.
        relevance: doc_id -> graded relevance (e.g. 0..3, or 0/1 for
            binary judgments). IDs not present are treated as 0 —
            "not judged" and "judged not relevant" are indistinguishable
            here by design (this harness has no partial-judgment pools).
        k: cutoff.

    Returns:
        0.0 if there are no relevant documents at all for this query
        (IDCG@k == 0) — a documented convention, not an error, so a
        query with zero labelled-relevant documents cannot silently
        contribute a NaN or divide-by-zero to an aggregate mean.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    gains = [relevance.get(doc_id, 0.0) for doc_id in ranked_ids]
    dcg = dcg_at_k(gains, k)
    ideal_gains = sorted(relevance.values(), reverse=True)
    idcg = dcg_at_k(ideal_gains, k) if ideal_gains else 0.0
    if idcg == 0:
        return 0.0
    return dcg / idcg


def mean_ndcg_at_k(
    per_query_ranked_ids: Iterable[Sequence[str]],
    per_query_relevance: Iterable[Mapping[str, float]],
    k: int,
) -> float:
    """Mean nDCG@k across a batch of queries (the number CI actually
    gates on). Queries with IDCG@k == 0 still count toward the mean at
    0.0 — do not filter them out silently, that would inflate the score
    by discarding hard queries."""
    values = [
        ndcg_at_k(ranked, rel, k)
        for ranked, rel in zip(per_query_ranked_ids, per_query_relevance)
    ]
    if not values:
        raise ValueError("no queries to average over")
    return sum(values) / len(values)
