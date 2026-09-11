"""Verification: is pooling type+format into one number per band (as
F113/F118/F120's own tables, and this ticket's routing table, did) hiding a
real facet-specific gap? Recomputes each band's accuracy SEPARATELY for
`type` and `format` (pooled across city only, not across facet), for both
the classifier's own value and the centroid-clean-CV embeddings prediction
-- same 253 labels, same estimator, same everything except the facet
pooling choice.

Run from the `eval` package venv:
    engine/packages/eval> .venv/Scripts/python.exe scripts/f120_facet_scoped_report.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

CALIB_DIR = Path(__file__).resolve().parents[1] / "data" / "calibration"
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from now_eval.calibration import embed_data as ed  # noqa: E402
from now_eval.calibration import embed_instrument as ei  # noqa: E402
from now_eval.calibration.adjudication import merge  # noqa: E402
from now_eval.calibration.finalize import type_format_population_counts  # noqa: E402
from now_eval.calibration.stats import estimate_cell_accuracy  # noqa: E402

BANDS = (0.95, 0.93, 0.75, 0.72, 0.45, 0.40)


def stable_perm(keys, seed):
    return sorted(range(len(keys)), key=lambda i: hashlib.sha256(f"{seed}:{keys[i]}".encode()).hexdigest())


def pool_one_facet(merged_rows, verdicts, predictions_by_key, pop_by_cell, facet, value):
    """Same math as mapping.combine_across_cells, but filtered to ONE facet,
    not pooled across both."""
    cell_estimates = ei.build_cell_estimates_for_predictions(merged_rows, verdicts, predictions_by_key, pop_by_cell)
    matching = [e for cell, e in cell_estimates.items() if cell.endswith(f":{facet}:{value}")]
    if not matching:
        return None
    n_total = sum(e.n_total for e in matching)
    n_sampled = sum(e.n_sampled for e in matching)
    n_agree = sum(e.n_agree for e in matching)
    n_disagree = sum(e.n_disagree for e in matching)
    n_agree_adj = sum(e.n_agree_adjudicated for e in matching)
    n_agree_adj_correct = sum(e.n_agree_adjudicated_correct for e in matching)
    n_disagree_correct = sum(e.n_disagree_adjudicated_correct_for_classifier for e in matching)
    return estimate_cell_accuracy(
        cell=f"{facet}:{value}", n_total=n_total, n_sampled=n_sampled, n_agree=n_agree, n_disagree=n_disagree,
        n_agree_adjudicated=n_agree_adj, n_agree_adjudicated_correct=n_agree_adj_correct,
        n_disagree_adjudicated_correct_for_classifier=n_disagree_correct,
    )


def main():
    sample_rows = [json.loads(l) for l in open(CALIB_DIR / "sample.jsonl", encoding="utf-8") if l.strip()]
    llm_labels = [json.loads(l) for l in open(CALIB_DIR / "llm_labels.jsonl", encoding="utf-8") if l.strip()]
    merged_rows = merge(sample_rows, llm_labels)
    verdicts = json.loads((CALIB_DIR / "calibration_verdicts.json").read_text(encoding="utf-8"))
    pop_by_cell = type_format_population_counts(REPO_ROOT)

    items = ed.load_labelled_items(CALIB_DIR)
    article_vecs = ed.fetch_article_vectors(items)
    items = [it for it in items if (it["city"], it["article_id"]) in article_vecs]
    for it in items:
        it["vec"] = article_vecs[(it["city"], it["article_id"])]
    by_facet = defaultdict(list)
    for it in items:
        by_facet[it["facet"]].append(it)

    classifier_preds = {it["key"]: it["classifier_value"] for it in items}

    cv_preds = {}
    for facet in ("type", "format"):
        tuples = [(it["key"], it["true_value"], it["vec"]) for it in by_facet[facet]]
        perm = stable_perm([t[0] for t in tuples], seed="f118-embed-centroid-cv-v1")
        for p in ei.cv_centroid_predictions(tuples, k_folds=5, seed_perm=perm):
            cv_preds[p.key] = p.predicted_value

    print(f"{'facet':>7} | {'band':>5} | {'n':>4} | {'cue-only acc':>12} | {'centroid-CV acc':>15}")
    for facet in ("type", "format"):
        for band in BANDS:
            cue_est = pool_one_facet(merged_rows, verdicts, classifier_preds, pop_by_cell, facet, band)
            cen_est = pool_one_facet(merged_rows, verdicts, cv_preds, pop_by_cell, facet, band)
            cue_acc = f"{cue_est.interval.point:.3f} [{cue_est.interval.low:.3f}-{cue_est.interval.high:.3f}]" if cue_est and cue_est.n_sampled else "n/a"
            cen_acc = f"{cen_est.interval.point:.3f} [{cen_est.interval.low:.3f}-{cen_est.interval.high:.3f}]" if cen_est and cen_est.n_sampled else "n/a"
            n = cue_est.n_sampled if cue_est else 0
            print(f"{facet:>7} | {band:>5.2f} | {n:>4} | {cue_acc:>12} | {cen_acc:>15}")


if __name__ == "__main__":
    main()
