"""E2.7 independent QA verification of nDCG@k / precision@k math.

Throwaway script. Not part of the product. Computes hand-derived values
INDEPENDENTLY (own invented fixtures + the Wikipedia worked example) and
compares them against now_eval.metrics.{ndcg,precision}.

Run from engine/packages/eval with: uv run python ../qa-verification/scripts/e27_metric_math_qa.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "eval" / "src"))

from now_eval.metrics.ndcg import dcg_at_k, ndcg_at_k
from now_eval.metrics.precision import precision_at_k


def check(name, expected, actual, tol=1e-9):
    ok = abs(expected - actual) < tol
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: expected={expected!r} actual={actual!r} diff={expected-actual:.3e}")
    return ok


all_ok = True

# ---------------------------------------------------------------
# 1) Own invented precision@6 example (>=8 items, binary relevance)
# ---------------------------------------------------------------
# Ranked list (best first), 8 items. Relevant set invented independently.
ranked8 = ["i1", "i2", "i3", "i4", "i5", "i6", "i7", "i8"]
relevant = {"i2", "i4", "i5", "i7", "i8"}  # relevant = 1, others = 0
# top-6 = i1..i6 -> relevance pattern: 0,1,0,1,1,0 -> 3 relevant hits
hand_precision_at_6 = 3 / 6  # = 0.5
lib_precision_at_6 = precision_at_k(ranked8, relevant, 6)
all_ok &= check("precision@6 (invented, 3/6 hits)", hand_precision_at_6, lib_precision_at_6)

# ---------------------------------------------------------------
# 2) Own invented nDCG@10 example, graded relevance 0-3, >=10 items
# ---------------------------------------------------------------
rels10 = [2, 0, 3, 1, 0, 2, 3, 0, 1, 1]
ids10 = [f"d{i}" for i in range(1, 11)]
relevance10 = dict(zip(ids10, rels10))

print("\n--- Hand DCG@10 (exponential gain) for", rels10, "---")
dcg_terms = []
for i, r in enumerate(rels10):
    rank = i + 1
    term = (2 ** r - 1) / math.log2(rank + 1)
    dcg_terms.append(term)
    print(f"  rank {rank}: rel={r} gain={2**r-1} disc=log2({rank+1})={math.log2(rank+1):.6f} term={term:.6f}")
hand_dcg10 = sum(dcg_terms)
print(f"  DCG@10 = {hand_dcg10:.6f}")

ideal10 = sorted(rels10, reverse=True)
print("  ideal order:", ideal10)
idcg_terms = []
for i, r in enumerate(ideal10):
    rank = i + 1
    term = (2 ** r - 1) / math.log2(rank + 1)
    idcg_terms.append(term)
    print(f"  ideal rank {rank}: rel={r} term={term:.6f}")
hand_idcg10 = sum(idcg_terms)
print(f"  IDCG@10 = {hand_idcg10:.6f}")
hand_ndcg10 = hand_dcg10 / hand_idcg10
print(f"  nDCG@10 = {hand_ndcg10:.6f}")

lib_dcg10 = dcg_at_k(rels10, 10)
lib_ndcg10 = ndcg_at_k(ids10, relevance10, 10)
all_ok &= check("DCG@10 (invented)", hand_dcg10, lib_dcg10)
all_ok &= check("nDCG@10 (invented)", hand_ndcg10, lib_ndcg10)

# ---------------------------------------------------------------
# 3) Wikipedia's own canonical example, verified from the live article
#    text (fetched via Wikipedia API, wikitext quoted in QA report),
#    NOT from memory and NOT from the package's test fixtures.
#    Relevances: 3,2,3,0,1,2 (documents D1..D6).
# ---------------------------------------------------------------
wiki_rels = [3, 2, 3, 0, 1, 2]
wiki_ids = ["D1", "D2", "D3", "D4", "D5", "D6"]

# 3a) Wikipedia's own DISPLAYED numeric table uses the LINEAR-gain
#     formula: DCG_p = sum(rel_i / log2(i+1)).  Confirm hand value
#     matches Wikipedia's stated DCG6 = 6.861 using linear gain (NOT
#     the exponential formula that now_eval implements).
def linear_dcg(rels, k):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels[:k]))

wiki_linear_dcg6 = linear_dcg(wiki_rels, 6)
check("Wikipedia linear DCG@6 (article states 6.861)", 6.861, wiki_linear_dcg6, tol=1e-3)

# Wikipedia's own IDCG for this example uses an EXTENDED ideal list that
# includes two documents (D7 rel=3, D8 rel=2) that are NOT in the
# original 6-item ranked list -- ideal list = [3,3,3,2,2,2,1,0], cut to
# top 6 -> [3,3,3,2,2,2]. This is Wikipedia's literal worked example,
# and it does NOT correspond to "resort the same 6 judgments".
wiki_extended_ideal = [3, 3, 3, 2, 2, 2]
wiki_linear_idcg6 = linear_dcg(wiki_extended_ideal, 6)
check("Wikipedia linear IDCG@6 w/ extended ideal list (article states 8.740)", 8.740, wiki_linear_idcg6, tol=1e-3)
wiki_ndcg6_as_published = wiki_linear_dcg6 / wiki_linear_idcg6
check("Wikipedia published nDCG@6 (article states 0.785)", 0.785, wiki_ndcg6_as_published, tol=1e-3)

# 3b) now_eval implements the EXPONENTIAL-gain formula instead (its own
#     docstring says so explicitly, and cites this as the formula
#     "nearly every IR paper/library means unless stated otherwise").
#     Hand-compute DCG/IDCG with EXPONENTIAL gain, using the SIMPLE
#     same-set IDCG (sort the SAME 6 judgments desc -- which is what
#     now_eval.ndcg_at_k actually does; it never sees D7/D8).
def exp_dcg(rels, k):
    return sum((2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(rels[:k]))

hand_exp_dcg6 = exp_dcg(wiki_rels, 6)
hand_exp_idcg6 = exp_dcg(sorted(wiki_rels, reverse=True), 6)
hand_exp_ndcg6 = hand_exp_dcg6 / hand_exp_idcg6
print(f"\nHand exponential-gain DCG@6={hand_exp_dcg6:.10f} IDCG@6={hand_exp_idcg6:.10f} nDCG@6={hand_exp_ndcg6:.10f}")

lib_ndcg6 = ndcg_at_k(wiki_ids, dict(zip(wiki_ids, wiki_rels)), 6)
lib_dcg6 = dcg_at_k(wiki_rels, 6)
all_ok &= check("now_eval dcg_at_k(wiki_rels, 6) matches hand exponential DCG", hand_exp_dcg6, lib_dcg6)
all_ok &= check("now_eval ndcg_at_k(...) matches hand exponential nDCG (same-set IDCG)", hand_exp_ndcg6, lib_ndcg6)

# 3c) Check the claim inside now_eval/metrics/ndcg.py's own docstring,
#     which asserts (in a comment) that this exact example gives
#     "nDCG@6 ~= 0.9608" for its exponential-gain implementation.
docstring_claim = 0.9608
print(f"\nndcg.py docstring claims nDCG@6 ~= {docstring_claim} for its OWN exponential formula on this example.")
print(f"Actual library output for that exact call: {lib_ndcg6:.6f}")
print(f"Actual value matching the WIDELY-CITED linear-gain/same-set-IDCG number "
      f"(6.861/7.141): {6.861/ (3+3/math.log2(3)+2/math.log2(4)+2/math.log2(5)+1/math.log2(6)):.6f}")
docstring_matches_impl = abs(docstring_claim - lib_ndcg6) < 1e-3
print(f"Does docstring's 0.9608 match the actual exponential-formula implementation output? {docstring_matches_impl}")

print("\n=== SUMMARY ===")
print("ALL NUMERIC CHECKS PASSED" if all_ok else "AT LEAST ONE NUMERIC CHECK FAILED")
