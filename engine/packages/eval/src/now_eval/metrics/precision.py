"""Precision@k / recall@k for set-relevance (binary) retrieval eval —
used for the related-articles gate (precision@6) and available generally.
"""
from __future__ import annotations

from collections.abc import Collection, Sequence


def precision_at_k(ranked_ids: Sequence[str], relevant_ids: Collection[str], k: int) -> float:
    """Fraction of the top-k results that are in the relevant set.

    Denominator is always k, not min(k, len(ranked_ids)): a surface that
    commits to filling k slots (§7 — every rail must fill) is penalized
    for returning fewer than k, not rewarded with a smaller denominator.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    relevant = set(relevant_ids)
    top_k = ranked_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant)
    return hits / k


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: Collection[str], k: int) -> float:
    """Fraction of all relevant docs surfaced in the top-k.

    Returns 0.0 (documented convention, not an error) when there are no
    relevant docs at all — mirrors ndcg_at_k's treatment of the same
    degenerate case so aggregate means behave consistently.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    top_k = ranked_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant)
    return hits / len(relevant)


def average_precision_at_k(ranked_ids: Sequence[str], relevant_ids: Collection[str], k: int) -> float:
    """Average Precision@k (area under the precision-recall curve up to
    k), for when rank order within the top-k matters, not just set
    membership. Not currently wired into a CI gate but exposed since
    related-articles precision@6 and search both plausibly want it once
    real systems exist.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    top_k = ranked_ids[:k]
    hits = 0
    precisions = []
    for i, doc_id in enumerate(top_k):
        if doc_id in relevant:
            hits += 1
            precisions.append(hits / (i + 1))
    if not precisions:
        return 0.0
    return sum(precisions) / min(len(relevant), k)


def mean_precision_at_k(
    per_query_ranked_ids: list[Sequence[str]],
    per_query_relevant_ids: list[Collection[str]],
    k: int,
) -> float:
    """Mean precision@k across a batch — the number CI actually gates on."""
    if not per_query_ranked_ids:
        raise ValueError("no queries to average over")
    values = [
        precision_at_k(ranked, relevant, k)
        for ranked, relevant in zip(per_query_ranked_ids, per_query_relevant_ids)
    ]
    return sum(values) / len(values)
