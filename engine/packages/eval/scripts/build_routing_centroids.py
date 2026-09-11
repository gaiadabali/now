"""F120 routing: build the production embeddings-centroid artifact that
`now_classifier.embed_routing` loads at classify-time.

Trained on ALL 253 human-adjudicated type/format labels (F118/F113's own
ground truth) -- NOT the 5-fold CV split `f118_embed_report.py` uses to
MEASURE this approach (that CV split exists only to get an honest
out-of-fold accuracy number; at deploy time there is no held-out concern,
these 253 items are simply the best training exemplars we have). Uses
`now_taxonomy_evidence.embed_similarity.build_trusted_centroids` (the exact
same function `now_eval`'s own measurement calls), which excludes any class
with fewer than `min_class_n` labelled exemplars from centroid candidacy
entirely -- F120 found `wellness`=2, `shop`=3 for `type` in this same
253-item set, too thin to trust.

Output: `engine/packages/classifier/data/embed_routing_centroids.json`,
version-controlled, read at classify-time with zero DB access.

Run from the `eval` package venv (needs the `calibration` extra):

    engine/packages/eval> .venv/Scripts/python.exe scripts/build_routing_centroids.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

CALIB_DIR = Path(__file__).resolve().parents[1] / "data" / "calibration"
REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_PATH = REPO_ROOT / "engine" / "packages" / "classifier" / "data" / "embed_routing_centroids.json"

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from now_eval.calibration import embed_data as ed  # noqa: E402
from now_taxonomy_evidence.embed_similarity import DEFAULT_MIN_CLASS_N, build_trusted_centroids  # noqa: E402


def main() -> None:
    items = ed.load_labelled_items(CALIB_DIR)
    article_vecs = ed.fetch_article_vectors(items)
    missing = [it for it in items if (it["city"], it["article_id"]) not in article_vecs]
    if missing:
        print(f"WARNING: {len(missing)}/{len(items)} labelled items have no article embedding -- excluded")
    items = [it for it in items if (it["city"], it["article_id"]) in article_vecs]
    for it in items:
        it["vec"] = article_vecs[(it["city"], it["article_id"])]

    by_facet: dict[str, list[tuple[str, list[float]]]] = defaultdict(list)
    for it in items:
        by_facet[it["facet"]].append((it["true_value"], it["vec"]))

    out = {"min_class_n": DEFAULT_MIN_CLASS_N, "source": "253-item F118/F113 human-adjudicated ground truth, ALL of it (no CV split -- see module docstring)", "facets": {}}
    for facet, labelled in by_facet.items():
        centroids, class_n, excluded = build_trusted_centroids(labelled, min_class_n=DEFAULT_MIN_CLASS_N)
        out["facets"][facet] = {
            "centroids": centroids,
            "class_n": class_n,
            "excluded_classes": sorted(excluded),
            "min_class_n": DEFAULT_MIN_CLASS_N,
        }
        print(f"{facet}: {len(labelled)} labelled items, {len(centroids)} trusted classes "
              f"(excluded: {sorted(excluded) or 'none'})")
        for cls, n in sorted(class_n.items(), key=lambda kv: kv[1]):
            flag = " EXCLUDED (< min_class_n)" if cls in excluded else ""
            print(f"    {cls}: n={n}{flag}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
