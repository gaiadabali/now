"""The embeddings-similarity instrument's pure vector math (cosine, class
centroids, nearest-centroid prediction) -- MOVED here from
`now_eval.calibration.embed_instrument` (F118 option a / F120 measured it;
this ticket -- "route now, LLM later" -- routes production traffic through
it for two of the four type/format bands). See PROGRESS.md F120's routing
decision.

Why this lives here and not in `now_eval` or `now_classifier`: both packages
already depend on `now-taxonomy-evidence` (the classifier for its cue
features/D10 resolution, eval's calibration extra for the same), so this is
the one shared, DB-free, dependency-light home that doesn't create a
backwards edge (a runtime package depending on the measurement/eval
package, or vice versa). `now_eval.calibration.embed_instrument` imports
these names back so its own (already-passing) unit tests and report
scripts are unaffected -- one implementation, two consumers, not a second
implementation.

No DB, no network, no numpy: plain `list[float]` vectors in, so a caller
holding either a JSON-decoded `engine.embeddings` row or a
`now_taxonomy_evidence.vectors.VectorSpace` row (`.tolist()`) can use it
directly.
"""
from __future__ import annotations

import math

Vector = list[float]


def cosine(a: Vector, b: Vector) -> float:
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def build_centroids(labelled: list[tuple[str, Vector]]) -> dict[str, Vector]:
    """`labelled`: (true_value, vector) pairs to build class means from.
    Mean, not re-normalised -- cosine similarity against an unnormalised
    centroid is still a valid ranking (cosine is scale-invariant in the
    query-to-centroid direction), and re-normalising would silently give
    every class the same weight regardless of how tight its cluster is."""
    buckets: dict[str, list[Vector]] = {}
    for val, vec in labelled:
        buckets.setdefault(val, []).append(vec)
    centroids: dict[str, Vector] = {}
    for val, vecs in buckets.items():
        dim = len(vecs[0])
        centroids[val] = [sum(v[d] for v in vecs) / len(vecs) for d in range(dim)]
    return centroids


def centroid_predict(vec: Vector, centroids: dict[str, Vector]) -> tuple[str, float]:
    """Nearest-mean argmax + margin (top1 cosine minus runner-up's)."""
    scored = sorted(((slug, cosine(vec, c)) for slug, c in centroids.items()),
                     key=lambda t: t[1], reverse=True)
    if not scored:
        return "", float("-inf")
    if len(scored) == 1:
        return scored[0][0], float("inf")
    return scored[0][0], scored[0][1] - scored[1][1]


# --------------------------------------------------------------------------
# F120 routing (this ticket): a class with too few labelled exemplars in the
# 253-item human-adjudicated set produces a centroid that is a mean of
# almost nothing -- F120 flagged `wellness`=2, `shop`=3 for `type` as
# exactly this case. Below `DEFAULT_MIN_CLASS_N` exemplars, a class is
# excluded from centroid candidacy ENTIRELY (not merely down-weighted): an
# article whose true class is thin can never be predicted by this model,
# which is a deliberate abstain, not a bug -- see `now_classifier.
# embed_routing` for how a caller must treat that (never silently forcing
# some other class to win by default, never inventing a confidence number
# for a class this measurement never validated).
# --------------------------------------------------------------------------

DEFAULT_MIN_CLASS_N = 5


def build_trusted_centroids(
    labelled: list[tuple[str, Vector]], min_class_n: int = DEFAULT_MIN_CLASS_N
) -> tuple[dict[str, Vector], dict[str, int], frozenset[str]]:
    """Returns (centroids, class_n, excluded_classes). `class_n` and
    `excluded_classes` are returned alongside the centroids themselves (not
    just logged) so a caller -- or a version-controlled artifact built from
    this -- can disclose exactly which classes were trusted and why,
    rather than a silent filter. Reused identically by the calibration
    measurement tooling (`now_eval`, to report per-class n honestly) and by
    the runtime routing artifact builder (`now_classifier`'s
    `embed_routing_centroids.json`), so both apply the exact same trust
    rule -- not two independently-tuned thresholds that could quietly
    drift apart."""
    class_n: dict[str, int] = {}
    for val, _ in labelled:
        class_n[val] = class_n.get(val, 0) + 1
    excluded = frozenset(v for v, n in class_n.items() if n < min_class_n)
    trusted = [(v, vec) for v, vec in labelled if v not in excluded]
    return build_centroids(trusted), class_n, excluded
