"""F120 routing re-measurement: after `now_classifier.embed_routing` routes
`category_fixed_{high,medium}` to the keyword-cue instrument and
`cue_{confident,fired}` to the embeddings-centroid instrument (see
PROGRESS.md F120's decision table), re-measure the COMBINED, routed system
against the identical 253 human-adjudicated labels, the identical
two-stage estimator (`stats.estimate_cell_accuracy` via
`embed_instrument.build_cell_estimates_for_predictions`), and the identical
six bands F118/F120 used -- so this table is directly comparable to both.

Per-item routed prediction, keyed off the item's OWN pre-routing
confidence band (0.95/0.93/0.75/0.72/0.45/0.40 -- the same six cells
F113/F118/F120 already partition the 253 items into):

    0.95 (category_fixed_high)   -> classifier's own value  (routes to keyword_cue)
    0.93 (cue_confident)         -> embeddings centroid, 5-fold CV (routes to embeddings_centroid)
    0.75 (category_fixed_medium) -> classifier's own value  (routes to keyword_cue)
    0.72 (cue_fired)             -> embeddings centroid, 5-fold CV (routes to embeddings_centroid)
    0.45, 0.40                   -> classifier's own value  (NOT routed -- out of scope, unchanged)

The embeddings prediction reuses `ei.cv_centroid_predictions` -- the exact
same leave-out-fold methodology F120 already used to measure the centroid
approach -- rather than the production artifact (`embed_routing_centroids
.json`, trained on ALL 253, no held-out fold): scoring the production
artifact against the same 253 items it was trained on would be
contaminated (an item would see its own label baked into the centroid it's
compared against), inflating the very number this report exists to check
honestly. The production artifact is correct for classifying NEW,
unlabelled articles (the actual ~4,514-row population this ticket routes);
this report's job is only to confirm that composing the two instruments
per-band, through the identical estimator, reproduces the numbers F118 and
F120 already established -- an integration/regression check on the
ROUTING LOGIC itself, not a new accuracy claim.

Run from the `eval` package venv:

    engine/packages/eval> .venv/Scripts/python.exe scripts/f120_routing_report.py
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
from now_eval.calibration.mapping import recommend  # noqa: E402

BANDS = (0.95, 0.93, 0.75, 0.72, 0.45, 0.40)
ROUTES_TO_EMBEDDINGS = {0.93, 0.72}
F118_CLASSIFIER_ACCURACY = {0.95: 0.66, 0.93: 0.45, 0.75: 0.61, 0.72: 0.283, 0.45: 0.417, 0.40: 0.312}
F120_CENTROID_ACCURACY = {0.95: 0.48, 0.93: 0.78, 0.75: 0.41, 0.72: 0.53}


def stable_perm(keys: list[str], seed: str) -> list[int]:
    return sorted(range(len(keys)), key=lambda i: hashlib.sha256(f"{seed}:{keys[i]}".encode()).hexdigest())


def main() -> None:
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
    by_facet: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        by_facet[it["facet"]].append(it)

    # Embeddings prediction per item: identical 5-fold CV as F120's own
    # measurement (same seed, same k_folds) -- see module docstring for why
    # this, not the production artifact, is the honest choice here.
    cv_pred_by_key: dict[str, str | None] = {}
    for facet in ("type", "format"):
        tuples = [(it["key"], it["true_value"], it["vec"]) for it in by_facet[facet]]
        perm = stable_perm([t[0] for t in tuples], seed="f118-embed-centroid-cv-v1")
        for p in ei.cv_centroid_predictions(tuples, k_folds=5, seed_perm=perm):
            cv_pred_by_key[p.key] = p.predicted_value

    routed_preds: dict[str, str | None] = {}
    routed_instrument_by_key: dict[str, str] = {}
    for it in items:
        band = round(it["original_confidence"], 2)
        if band in ROUTES_TO_EMBEDDINGS:
            routed_preds[it["key"]] = cv_pred_by_key.get(it["key"])
            routed_instrument_by_key[it["key"]] = "embeddings_centroid"
        else:
            routed_preds[it["key"]] = it["classifier_value"]
            routed_instrument_by_key[it["key"]] = "keyword_cue (unrouted)" if band in (0.45, 0.40) else "keyword_cue"

    estimates = ei.build_cell_estimates_for_predictions(merged_rows, verdicts, routed_preds, pop_by_cell)

    print("=== F120 ROUTING RE-MEASUREMENT: routed system vs. F118 (cue-only) vs. F120 (centroid-CV-only) ===\n")
    print(f"{'band':>6} | {'n':>4} | {'routed acc':>10} | {'95% CI':>17} | {'F118 cue':>9} | {'F120 centroid':>13} | instrument used | gate?")
    any_mismatch = False
    for band in BANDS:
        rec = recommend(band, estimates)
        instrument = ("embeddings_centroid" if band in ROUTES_TO_EMBEDDINGS
                      else ("keyword_cue (routed)" if band in (0.95, 0.75) else "keyword_cue (unrouted, out of scope)"))
        cue_acc = F118_CLASSIFIER_ACCURACY[band]
        cen_acc = F120_CENTROID_ACCURACY.get(band)
        if rec.recommended_number is None:
            print(f"{band:>6.2f} | {rec.n_sampled:>4} | {'n/a':>10} | {'':>17} | {cue_acc:>9.3f} | "
                  f"{('%.3f' % cen_acc) if cen_acc is not None else 'n/a':>13} | {instrument} |")
            continue
        gate = "CROSSES 0.85" if rec.crosses_gate_after else ""
        ci = f"[{rec.accuracy_low:.3f}-{rec.accuracy_high:.3f}]"
        print(f"{band:>6.2f} | {rec.n_sampled:>4} | {rec.recommended_number:>10.3f} | {ci:>17} | {cue_acc:>9.3f} | "
              f"{('%.3f' % cen_acc) if cen_acc is not None else 'n/a':>13} | {instrument} | {gate}")

        # Integration check: the routed number for this band should equal
        # (within adjudicated-sample noise -- it can differ slightly from
        # the exact published number if population counts shifted since
        # F118/F120 ran) the winning instrument's own published number.
        expected = cue_acc if band in (0.95, 0.75, 0.45, 0.40) else cen_acc
        if expected is not None and rec.recommended_number is not None:
            if abs(rec.recommended_number - expected) > 0.02:
                any_mismatch = True
                print(f"         ^^ WARNING: routed accuracy {rec.recommended_number:.3f} diverges from the "
                      f"expected winning-instrument number {expected:.3f} by more than 0.02 -- check the "
                      f"routing wiring before trusting this band.")

    print()
    if any_mismatch:
        print("RESULT (pooled): at least one band's routed, end-to-end accuracy diverges from what F118/F120 "
              "already published for the winning instrument on that band -- DO NOT SHIP. Investigate before "
              "proceeding.")
    else:
        print("RESULT (pooled): every routed band reproduces (within noise) the winning instrument's own "
              "published F118/F120 number, through the identical two-stage estimator -- the routing wiring is "
              "verified to compose the two instruments correctly, band for band.")

    # ---------------- Facet-scoped validation against the ACTUAL committed constants ----------------
    # A pooled number can hide a real per-facet gap -- caught live during
    # this ticket (`format`'s true per-band accuracy diverges meaningfully
    # from `type`'s; a pooled number would have overstated format's
    # accuracy at 3 of 4 routed bands). This section re-measures type and
    # format SEPARATELY and checks each against the exact facet-scoped
    # constant `now_classifier.embed_routing.ROUTED_CONFIDENCE` will
    # actually stamp -- the module the classifier really imports, not a
    # copy of its numbers.
    print("\n=== FACET-SCOPED validation against now_classifier.embed_routing.ROUTED_CONFIDENCE ===\n")
    sys.path.insert(0, str((REPO_ROOT / "engine" / "packages" / "classifier" / "src")))
    from now_classifier.embed_routing import ROUTED_CONFIDENCE  # noqa: E402

    from now_eval.calibration.stats import estimate_cell_accuracy  # noqa: E402

    def pool_one_facet(facet, value, predictions_by_key):
        cell_estimates = ei.build_cell_estimates_for_predictions(merged_rows, verdicts, predictions_by_key, pop_by_cell)
        matching = [e for cell, e in cell_estimates.items() if cell.endswith(f":{facet}:{value}")]
        if not matching:
            return None
        return estimate_cell_accuracy(
            cell=f"{facet}:{value}",
            n_total=sum(e.n_total for e in matching), n_sampled=sum(e.n_sampled for e in matching),
            n_agree=sum(e.n_agree for e in matching), n_disagree=sum(e.n_disagree for e in matching),
            n_agree_adjudicated=sum(e.n_agree_adjudicated for e in matching),
            n_agree_adjudicated_correct=sum(e.n_agree_adjudicated_correct for e in matching),
            n_disagree_adjudicated_correct_for_classifier=sum(e.n_disagree_adjudicated_correct_for_classifier for e in matching),
        )

    classifier_preds = {it["key"]: it["classifier_value"] for it in items}
    facet_mismatch = False
    band_to_route_name = {0.95: "category_fixed_high", 0.93: "cue_confident", 0.75: "category_fixed_medium", 0.72: "cue_fired"}
    for band, route_name in band_to_route_name.items():
        preds = cv_pred_by_key if band in ROUTES_TO_EMBEDDINGS else classifier_preds
        for facet in ("type", "format"):
            est = pool_one_facet(facet, band, preds)
            measured = est.interval.point if est and est.n_sampled else None
            committed = ROUTED_CONFIDENCE[(route_name, facet)]
            status = "n/a (no adjudicated data)" if measured is None else (
                "OK" if abs(measured - committed) <= 0.02 else "MISMATCH")
            if status == "MISMATCH":
                facet_mismatch = True
            print(f"  band={band:.2f} facet={facet:>6}: re-measured={('%.3f' % measured) if measured is not None else 'n/a':>6}  "
                  f"committed={committed:.3f}  [{status}]")

    print()
    if facet_mismatch:
        print("RESULT (facet-scoped): at least one facet-specific committed number in embed_routing.py "
              "diverges from a live re-measurement -- DO NOT SHIP, fix ROUTED_CONFIDENCE before proceeding.")
    else:
        print("RESULT (facet-scoped): every committed (band, facet) number in "
              "now_classifier.embed_routing.ROUTED_CONFIDENCE reproduces this live re-measurement -- verified, "
              "not assumed.")


if __name__ == "__main__":
    main()
