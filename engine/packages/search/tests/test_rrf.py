"""Pure-Python tests for Reciprocal Rank Fusion -- no DB, no network,
always runs in CI. Verifies the formula literally against ARCHITECTURE.md
§7: score = sum 1/(k + rank_i)."""

from __future__ import annotations

import pytest

from now_search.models import RankedHit
from now_search.rrf import DEFAULT_K, reciprocal_rank_fusion, to_ranked_hits


def rh(entity_id: str, rank: int, score: float = 1.0) -> RankedHit:
    return RankedHit(entity_id=entity_id, rank=rank, raw_score=score)


def test_doc_in_both_lists_sums_both_terms():
    lexical = [rh("A", 1), rh("B", 2)]
    semantic = [rh("A", 3), rh("C", 1)]
    fused = reciprocal_rank_fusion(lexical, semantic, k=60)
    by_id = {h.entity_id: h for h in fused}

    assert by_id["A"].rrf_score == pytest.approx(1 / 61 + 1 / 63)
    assert by_id["B"].rrf_score == pytest.approx(1 / 62)
    assert by_id["C"].rrf_score == pytest.approx(1 / 61)
    assert by_id["A"].lexical_rank == 1
    assert by_id["A"].semantic_rank == 3
    assert by_id["B"].semantic_rank is None
    assert by_id["C"].lexical_rank is None


def test_union_not_intersection_every_doc_from_either_list_appears():
    lexical = [rh("only-lexical", 1)]
    semantic = [rh("only-semantic", 1)]
    fused = reciprocal_rank_fusion(lexical, semantic)
    assert {h.entity_id for h in fused} == {"only-lexical", "only-semantic"}


def test_sorted_best_first_by_score_desc():
    lexical = [rh("A", 1), rh("B", 2), rh("C", 3)]
    semantic = [rh("A", 1), rh("B", 1), rh("C", 100)]
    fused = reciprocal_rank_fusion(lexical, semantic)
    scores = [h.rrf_score for h in fused]
    assert scores == sorted(scores, reverse=True)
    # A: rank1+rank1 (best in both) must outrank everything else here.
    assert fused[0].entity_id == "A"


def test_empty_lists_produce_empty_result():
    assert reciprocal_rank_fusion([], []) == []


def test_deterministic_tie_break_by_entity_id():
    # Two docs with identical rank in both lists -> identical rrf_score;
    # output order must still be deterministic (sorted by entity_id).
    lexical = [rh("z", 1), rh("a", 2)]
    semantic = [rh("z", 2), rh("a", 1)]
    fused = reciprocal_rank_fusion(lexical, semantic)
    assert fused[0].rrf_score == pytest.approx(fused[1].rrf_score)
    assert fused[0].entity_id == "a"  # 'a' < 'z' lexicographically


def test_default_k_matches_architecture_doc():
    assert DEFAULT_K == 60


def test_to_ranked_hits_assigns_1_indexed_rank_by_position():
    hits = to_ranked_hits([("x", 0.9), ("y", 0.5), ("z", 0.1)])
    assert [h.rank for h in hits] == [1, 2, 3]
    assert [h.entity_id for h in hits] == ["x", "y", "z"]
    assert hits[0].raw_score == 0.9
