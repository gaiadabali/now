"""F118(a) -- measure the embeddings-based type/format instrument against
the same ground truth F113 used to measure the cue instrument, using the
SAME two-stage population-weighted estimator (`stats.estimate_cell_accuracy`
via `embed_instrument.build_cell_estimates_for_predictions`), so every
number below is directly comparable, band-for-band, to F118's own table.
Run from the `eval` package venv:

    engine/packages/eval> .venv/Scripts/python.exe scripts/f118_embed_report.py
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
from now_eval.calibration.mapping import recommend  # noqa: E402
from now_eval.calibration.finalize import type_format_population_counts  # noqa: E402

BANDS = (0.95, 0.93, 0.75, 0.72, 0.45, 0.40)
F118_CLASSIFIER_ACCURACY = {0.95: 0.66, 0.93: 0.45, 0.75: 0.61, 0.72: 0.283, 0.45: 0.417, 0.40: 0.312}


def stable_perm(keys: list[str], seed: str) -> list[int]:
    return sorted(range(len(keys)), key=lambda i: hashlib.sha256(f"{seed}:{keys[i]}".encode()).hexdigest())


def report_method(label: str, merged_rows: list[dict], verdicts: dict, predictions_by_key: dict, pop_by_cell: dict) -> dict:
    estimates = ei.build_cell_estimates_for_predictions(merged_rows, verdicts, predictions_by_key, pop_by_cell)
    print(f"=== {label} ===")
    row_out = {}
    for value in BANDS:
        rec = recommend(value, estimates)
        row_out[value] = rec.recommended_number
        cls_acc = F118_CLASSIFIER_ACCURACY[value]
        if rec.recommended_number is None:
            print(f"  {value:.2f}: n={rec.n_sampled:3d}  (no adjudicated data)   [classifier was {cls_acc}]")
        else:
            gate = "CROSSES 0.85" if rec.crosses_gate_after else ""
            print(f"  {value:.2f}: n={rec.n_sampled:3d}  accuracy={rec.recommended_number:.3f} "
                  f"[{rec.accuracy_low:.3f}-{rec.accuracy_high:.3f}]  (classifier was {cls_acc}) {gate}")
    print()
    return row_out


def main() -> None:
    sample_rows = [json.loads(l) for l in open(CALIB_DIR / "sample.jsonl", encoding="utf-8") if l.strip()]
    llm_labels = [json.loads(l) for l in open(CALIB_DIR / "llm_labels.jsonl", encoding="utf-8") if l.strip()]
    merged_rows = merge(sample_rows, llm_labels)  # 420 rows -- NOT just the 253 adjudicated
    verdicts = json.loads((CALIB_DIR / "calibration_verdicts.json").read_text(encoding="utf-8"))
    print(f"merged_rows (sampled, pre-adjudication filter): {len(merged_rows)}; adjudicated verdicts: {len(verdicts)}\n")

    pop_by_cell = type_format_population_counts(REPO_ROOT)

    items = ed.load_labelled_items(CALIB_DIR)  # the 253 with known true_value, + vectors below
    article_vecs = ed.fetch_article_vectors(items)
    missing = [it for it in items if (it["city"], it["article_id"]) not in article_vecs]
    if missing:
        print(f"WARNING: {len(missing)}/{len(items)} adjudicated items have no article embedding -- excluded")
    items = [it for it in items if (it["city"], it["article_id"]) in article_vecs]
    for it in items:
        it["vec"] = article_vecs[(it["city"], it["article_id"])]
    by_facet: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        by_facet[it["facet"]].append(it)

    results: dict[str, dict] = {}

    # ---------------- classifier's own accuracy, recomputed the same way, as the reproduction check ----------------
    classifier_preds = {it["key"]: it["classifier_value"] for it in items}
    results["classifier (F113 reproduction check)"] = report_method(
        "CLASSIFIER (reproduction check -- must equal F118's own numbers)",
        merged_rows, verdicts, classifier_preds, pop_by_cell,
    )

    # ---------------- Approach 1: zero-shot term similarity ----------------
    bare_terms = {f: ed.fetch_stored_term_vectors(f) for f in ("type", "format")}
    rich_terms = ed.load_rich_term_vectors(CALIB_DIR / "term_vectors_rich.json")

    for variant_name, terms in (("BARE term text (already stored)", bare_terms), ("RICH term text (hand-authored descriptions)", rich_terms)):
        preds = {}
        for facet in ("type", "format"):
            for it in by_facet[facet]:
                pred, _ = ei.zero_shot_predict(it["vec"], terms[facet])
                preds[it["key"]] = pred
        results[f"zero-shot / {variant_name}"] = report_method(
            f"APPROACH 1: zero-shot term similarity -- {variant_name}",
            merged_rows, verdicts, preds, pop_by_cell,
        )

    # ---------------- Approach 2: kNN LOO over the labelled set ----------------
    for k in (5, 9, 15):
        preds = {}
        for facet in ("type", "format"):
            tuples = [(it["key"], it["true_value"], it["vec"]) for it in by_facet[facet]]
            loo = ei.loo_knn_predictions(tuples, k)
            for p in loo:
                preds[p.key] = p.predicted_value
        results[f"kNN k={k}"] = report_method(f"APPROACH 2: kNN leave-one-out, k={k}", merged_rows, verdicts, preds, pop_by_cell)

    # ---------------- Approach 3a: centroid, clean (CV) ----------------
    preds = {}
    for facet in ("type", "format"):
        tuples = [(it["key"], it["true_value"], it["vec"]) for it in by_facet[facet]]
        perm = stable_perm([t[0] for t in tuples], seed="f118-embed-centroid-cv-v1")
        cv_preds = ei.cv_centroid_predictions(tuples, k_folds=5, seed_perm=perm)
        for p in cv_preds:
            preds[p.key] = p.predicted_value
    results["centroid clean (5-fold CV)"] = report_method("APPROACH 3a: centroid, CLEAN (5-fold CV on true labels)", merged_rows, verdicts, preds, pop_by_cell)

    # ---------------- Approach 3b: centroid, contaminated (bulk classifier labels) ----------------
    exclude_by_city: dict[str, set] = defaultdict(set)
    for it in items:
        exclude_by_city[it["city"]].add(it["wp_id"])
    preds = {}
    for facet in ("type", "format"):
        bulk = ed.fetch_bulk_corpus(facet, exclude_by_city)
        centroids = ei.build_centroids(bulk)
        for it in by_facet[facet]:
            pred, _ = ei.centroid_predict(it["vec"], centroids)
            preds[it["key"]] = pred
    results["centroid CONTAMINATED (bulk auto-applied labels)"] = report_method(
        "APPROACH 3b: centroid, CONTAMINATED (bulk classifier-assigned labels, articles in labelled set excluded)",
        merged_rows, verdicts, preds, pop_by_cell,
    )

    # ---------------- Supplementary: own-margin coverage curves ----------------
    # NOT population-weighted -- computed directly over the 253-item
    # adjudicated sample, which deliberately over-samples disagreements
    # (PROVENANCE.md §8.2/8.4), so these coverage fractions are NOT
    # representative of the real corpus. They exist to answer a narrower
    # question: does thresholding on the METHOD'S OWN margin (its
    # nearest-vs-runner-up gap, the only self-reported confidence an
    # unsupervised/CV method has) trade coverage for accuracy in the
    # direction a real gate would need -- i.e. is there a margin threshold
    # this instrument could plausibly ship at all.
    print("=== SUPPLEMENTARY: own-margin coverage curves (WITHIN adjudicated sample, NOT population-weighted) ===\n")
    thresholds = [-1.0, 0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20]

    def print_curve(label: str, predictions: list[ei.Prediction]) -> None:
        curve = ei.coverage_curve(predictions, thresholds)
        n_correct, n, acc = ei.overall_accuracy(predictions)
        print(f"-- {label} -- all {n} adjudicated items: {n_correct}/{n} = {acc:.3f}")
        for pt in curve:
            if pt.n_applied:
                print(f"     margin>={pt.threshold:+.3f}: within-sample coverage={pt.coverage:.2f} (n={pt.n_applied:3d}) accuracy={pt.accuracy:.3f}")
        print()

    for facet in ("type", "format"):
        tuples = [(it["key"], it["true_value"], it["vec"]) for it in by_facet[facet]]
        perm = stable_perm([t[0] for t in tuples], seed="f118-embed-centroid-cv-v1")
        print_curve(f"{facet} / centroid clean CV", ei.cv_centroid_predictions(tuples, k_folds=5, seed_perm=perm))
        print_curve(f"{facet} / kNN k=9 LOO", ei.loo_knn_predictions(tuples, 9))
        preds_rich = [ei.Prediction(key=it["key"], true_value=it["true_value"],
                                     predicted_value=(r := ei.zero_shot_predict(it["vec"], rich_terms[facet]))[0], margin=r[1])
                      for it in by_facet[facet]]
        print_curve(f"{facet} / zero-shot RICH", preds_rich)

    # ---------------- Combination: classifier + best embeddings method ----------------
    # Raw subsample only (disagreement-enriched, not population-weighted --
    # same caveat as the supplementary section): measures whether the two
    # instruments agreeing is itself a useful signal, per the brief's
    # instruction to measure a combination rather than assume it helps.
    print("=== COMBINATION (raw subsample): classifier proposal vs. centroid-clean CV prediction ===\n")
    for facet in ("type", "format"):
        tuples = [(it["key"], it["true_value"], it["vec"]) for it in by_facet[facet]]
        perm = stable_perm([t[0] for t in tuples], seed="f118-embed-centroid-cv-v1")
        cv_preds = {p.key: p.predicted_value for p in ei.cv_centroid_predictions(tuples, k_folds=5, seed_perm=perm)}
        agree, disagree = [], []
        for it in by_facet[facet]:
            p = ei.Prediction(key=it["key"], true_value=it["true_value"], predicted_value=it["classifier_value"], margin=0.0)
            (agree if cv_preds.get(it["key"]) == it["classifier_value"] else disagree).append(p)
        _, n_a, acc_a = ei.overall_accuracy(agree)
        _, n_d, acc_d = ei.overall_accuracy(disagree)
        total = len(by_facet[facet])
        print(f"  {facet}: classifier==centroid on {n_a}/{total} ({n_a/total:.2f} of subsample), classifier accuracy there = {acc_a:.3f}")
        print(f"  {facet}: classifier!=centroid on {n_d}/{total}, classifier accuracy there = {acc_d:.3f}  <- where they disagree, classifier is right this often")
    print()

    # ---------------- Summary table ----------------
    print("=== SUMMARY: recommended_number per band (None = no adjudicated data in that cell) ===")
    header = ["band"] + list(results.keys())
    print(" | ".join(header))
    for value in BANDS:
        row = [f"{value:.2f}"] + [f"{results[m].get(value)}" for m in results]
        print(" | ".join(row))


if __name__ == "__main__":
    main()
