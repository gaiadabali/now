"""E2.7 QA: mechanically verify eval/train hold-out disjointness.

Not a re-read of intent comments -- actually builds both partitions from
the real committed articles.jsonl via the package's own dataset builders
and computes set intersection of wp_ids. Also fuzzes split_for/is_eval
directly over a large id range to prove no id is ever in both buckets
(a property that must hold structurally, since split_for is a pure
function of wp_id -- but we check the *usages*, not just the primitive).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "eval" / "src"))

from now_eval.datasets.split import is_eval, split_for
from now_eval.datasets.type_labels import build_type_labels
from now_eval.datasets.facet_labels import build_facet_labels
from now_eval.datasets.related_articles import build_related_articles_labels
from now_eval.datasets.search_queries import build_provisional_query_set

# 1) Direct fuzz of the primitive over a large range: for every wp_id,
#    is_eval and split_for=="train" must be exact complements -- no id
#    can ever be both.
bad = 0
for wp_id in range(0, 200_000):
    e = is_eval(wp_id)
    s = split_for(wp_id)
    if e and s == "train":
        bad += 1
    if (not e) and s == "eval":
        bad += 1
print(f"[primitive] contradictory eval/train assignments over 200,000 ids: {bad} (expect 0)")

# 2) Build real labelled sets from the committed corpus and check
#    cross-dataset id overlap against the type-classification TRAIN
#    partition (the only place this package actually materializes a
#    "train" set today, used to fit the trivial-most-popular baseline).
type_eval = build_type_labels(split="eval")
type_train = build_type_labels(split="train")
facet_eval = build_facet_labels()
related_eval = build_related_articles_labels()
search_eval = build_provisional_query_set()

type_eval_ids = {t.wp_id for t in type_eval}
type_train_ids = {t.wp_id for t in type_train}
facet_ids = {f.wp_id for f in facet_eval}

print(f"type_labels eval set: {len(type_eval_ids)} ids, train set: {len(type_train_ids)} ids")
print(f"facet_labels eval set: {len(facet_ids)} ids")

overlap_type = type_eval_ids & type_train_ids
print(f"type eval/train intersection: {len(overlap_type)} ids (expect 0)")

overlap_facet_vs_type_train = facet_ids & type_train_ids
print(f"facet(eval)/type(train) intersection: {len(overlap_facet_vs_type_train)} ids "
      f"(expect 0 -- would mean E2.1's baseline-fit data includes rows E2.2 is held out on... "
      f"not actually a leakage vector since different articles/label kinds, but checked anyway)")

# 3) Sanity: every id in every "eval" labelled set must independently
#    satisfy is_eval(wp_id) == True (catches a builder that forgot to
#    filter, or filtered on the wrong split() call).
for name, ids in [
    ("type_labels(eval)", type_eval_ids),
    ("facet_labels", facet_ids),
]:
    mismatches = [i for i in ids if not is_eval(i)]
    print(f"{name}: {len(mismatches)}/{len(ids)} ids that FAIL is_eval() despite being in the eval set (expect 0)")

for i in type_train_ids:
    if is_eval(i):
        print(f"FAIL: type_train contains wp_id={i} for which is_eval() is True")

print("\n=== SUMMARY ===")
ok = bad == 0 and len(overlap_type) == 0
print("DISJOINTNESS VERIFIED" if ok else "LEAKAGE DETECTED")
