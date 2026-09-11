"""F118 option (a) -- the embeddings-based type/format instrument.

Evaluates three embeddings approaches (zero-shot term similarity, kNN over
the 253-item labelled set, class centroids) against the same 253
human-adjudicated type/format ground-truth labels F113/F111 already
established, using the same two-stage adjudication this package already
trusts (see `adjudication.py`, `analyze.py`, `stats.py`).

**Ground truth extraction, stated precisely** (see PROGRESS.md F118 and
`PROVENANCE.md` §8.4): `calibration_verdicts.json` records, for each of the
253 adjudicated items, whether Hansel ruled the classifier's proposed
value correct (`"classifier"`) or the blind LLM's proposed value correct
(`"llm"`) -- verified directly (see module-level check in the report
script) that no item was ruled `"neither"`/`"both_wrong"`, so every one of
the 253 has a known true value: the classifier's `proposed_value` when the
verdict is `"classifier"`, the LLM's labelled value when the verdict is
`"llm"` (and for the 42 control items, an agreement, the two values are
identical by construction). This reuses precisely the same ground truth
`analyze.build_cell_estimates` uses to score the *classifier* -- here it
scores the *embeddings instrument* against the identical 253 labels
instead, which is what makes the two numbers comparable.

This module is pure logic (cosine similarity, kNN voting, centroid
classification, coverage/accuracy curves) -- no DB, no network -- so it is
unit-testable without the `calibration` extra, matching `stats.py`'s
convention. DB-touching data loading lives in
`now_eval.calibration.embed_data` (imported lazily by the report script),
kept separate for the same reason `db_frame.py` is separate from
`analyze.py`.

**F120 routing update:** `cosine`/`build_centroids`/`centroid_predict` (the
pieces this ticket's production routing also needs, see PROGRESS.md F120)
have MOVED to `now_taxonomy_evidence.embed_similarity` -- imported back
below and re-exported under their original names so every existing
caller/test in this package is unaffected. Not a second implementation:
the runtime classifier (`now_classifier.embed_routing`) and this
measurement module now both call the identical functions.
`now_taxonomy_evidence` moves from this package's `calibration` extra into
its core `dependencies` accordingly (see `pyproject.toml`) -- required
because this module is imported without the extra (the promise above), so
the import must resolve unconditionally. Its own `__init__.py` does no
eager heavy import, so this costs nothing at import time beyond
`now-eval`'s existing footprint; it is a real (if light) new install-time
dependency, disclosed here rather than silently added.
"""
from __future__ import annotations

from dataclasses import dataclass

from now_taxonomy_evidence.embed_similarity import (  # noqa: F401 -- re-exported, see docstring above
    Vector,
    build_centroids,
    centroid_predict,
    cosine,
)


@dataclass(frozen=True)
class Prediction:
    key: str            # "{city}:{wp_id}:{facet}"
    true_value: str
    predicted_value: str | None   # None = abstained (no candidate at all)
    margin: float                  # top1_score - top2_score; -inf if <2 candidates


# --------------------------------------------------------------------------
# Approach 1: zero-shot term similarity
# --------------------------------------------------------------------------


def zero_shot_predict(article_vec: Vector, term_vecs: dict[str, Vector]) -> tuple[str, float]:
    """Returns (best_slug, margin) -- margin is top1 cosine minus the
    runner-up's, our confidence proxy since there is no learned threshold
    here (this is genuinely zero-shot: no label was used to produce it)."""
    scored = sorted(((slug, cosine(article_vec, vec)) for slug, vec in term_vecs.items()),
                     key=lambda t: t[1], reverse=True)
    if not scored:
        return "", float("-inf")
    if len(scored) == 1:
        return scored[0][0], float("inf")
    return scored[0][0], scored[0][1] - scored[1][1]


# --------------------------------------------------------------------------
# Approach 2: kNN over the labelled set (leave-one-out)
# --------------------------------------------------------------------------


def knn_predict(query_vec: Vector, neighbours: list[tuple[str, Vector]], k: int) -> tuple[str, float]:
    """`neighbours`: (true_value, vector) pairs EXCLUDING the query item
    itself (caller's responsibility -- see `loo_knn_predictions`, which
    enforces this by construction rather than trusting the caller each
    time). Vote is similarity-weighted (each neighbour's cosine score, not
    a flat 1/k) so a lopsided top match counts more than a marginal one;
    margin is the winning class's vote share minus the runner-up's."""
    scored = sorted(((val, cosine(query_vec, vec)) for val, vec in neighbours),
                     key=lambda t: t[1], reverse=True)[:k]
    if not scored:
        return "", float("-inf")
    votes: dict[str, float] = {}
    for val, sim in scored:
        votes[val] = votes.get(val, 0.0) + max(sim, 0.0)
    total = sum(votes.values()) or 1.0
    ranked = sorted(votes.items(), key=lambda t: t[1], reverse=True)
    top_val, top_vote = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    return top_val, (top_vote - runner_up) / total


def loo_knn_predictions(items: list[tuple[str, str, Vector]], k: int) -> list[Prediction]:
    """`items`: (key, true_value, vector) for one facet's labelled pool.
    Leave-one-out: every prediction excludes its own item from the voting
    pool, so no item ever sees its own label -- the only honest way to
    measure kNN accuracy on a pool this size (253 total, ~120-130 per
    facet) where a held-out split would waste too much of an already-thin
    sample."""
    out = []
    for i, (key, true_val, vec) in enumerate(items):
        pool = [(v, vc) for j, (_, v, vc) in enumerate(items) if j != i]
        pred, margin = knn_predict(vec, pool, k)
        out.append(Prediction(key=key, true_value=true_val, predicted_value=pred or None, margin=margin))
    return out


# --------------------------------------------------------------------------
# Approach 3: centroid / prototype
#
# `build_centroids`/`centroid_predict` moved to
# `now_taxonomy_evidence.embed_similarity` (imported at module top) -- see
# this module's docstring.
# --------------------------------------------------------------------------


def kfold_indices(n: int, k_folds: int, seed_perm: list[int]) -> list[list[int]]:
    """Splits a pre-shuffled index permutation into `k_folds` near-equal
    folds. `seed_perm` is supplied by the caller (a deterministic shuffle,
    e.g. sorted-by-hash) rather than computed here, so this stays free of
    any RNG -- reproducibility matters more than convenience at n=253."""
    folds: list[list[int]] = [[] for _ in range(k_folds)]
    for i, idx in enumerate(seed_perm):
        folds[i % k_folds].append(idx)
    return folds


def cv_centroid_predictions(items: list[tuple[str, str, Vector]], k_folds: int, seed_perm: list[int]) -> list[Prediction]:
    """`items`: (key, true_value, vector). Stratified-ish k-fold (via the
    caller's permutation) -- centroids for a fold's test items are built
    ONLY from the other folds' true labels, so no item's own label ever
    contributes to the centroid that classifies it (the contamination
    `stats.py`/F118's brief explicitly warns about)."""
    n = len(items)
    folds = kfold_indices(n, k_folds, seed_perm)
    out: list[Prediction] = []
    for fold in folds:
        test_idx = set(fold)
        train = [(items[i][1], items[i][2]) for i in range(n) if i not in test_idx]
        centroids = build_centroids(train)
        for i in fold:
            key, true_val, vec = items[i]
            pred, margin = centroid_predict(vec, centroids)
            out.append(Prediction(key=key, true_value=true_val, predicted_value=pred or None, margin=margin))
    return out


# --------------------------------------------------------------------------
# Coverage/accuracy curves -- same shape as F113's confidence bands, so a
# threshold on OUR margin plays the role the invented confidence.py numbers
# played for the cue instrument, and the resulting table is directly
# comparable to F118's.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CoveragePoint:
    threshold: float
    coverage: float     # fraction of the pool this threshold would auto-apply
    n_applied: int
    accuracy: float      # accuracy among the applied subset
    n_correct: int


def coverage_curve(predictions: list[Prediction], thresholds: list[float]) -> list[CoveragePoint]:
    n_total = len(predictions)
    out = []
    for t in thresholds:
        applied = [p for p in predictions if p.margin >= t and p.predicted_value is not None]
        n = len(applied)
        correct = sum(1 for p in applied if p.predicted_value == p.true_value)
        out.append(CoveragePoint(
            threshold=t,
            coverage=n / n_total if n_total else float("nan"),
            n_applied=n,
            accuracy=correct / n if n else float("nan"),
            n_correct=correct,
        ))
    return out


def overall_accuracy(predictions: list[Prediction]) -> tuple[int, int, float]:
    n = len(predictions)
    correct = sum(1 for p in predictions if p.predicted_value == p.true_value)
    return correct, n, (correct / n if n else float("nan"))


# --------------------------------------------------------------------------
# Population-weighted, two-stage accuracy per ORIGINAL confidence band --
# this is what makes an embeddings method's numbers directly comparable to
# F118's table, rather than to a raw accuracy over the (deliberately
# disagreement-enriched) 253-item adjudicated subsample, which is a
# harder, non-representative slice (`analyze.build_cell_estimates`
# computes the exact same thing for the CLASSIFIER; this is that same
# machinery, generalised to score any predictor's `predicted_value`
# against the same ground truth).
# --------------------------------------------------------------------------


def build_cell_estimates_for_predictions(
    merged_rows: list[dict],
    verdicts: dict[str, str],
    predictions_by_key: dict[str, str | None],
    population_by_cell: dict[str, int],
):
    """`merged_rows`: the full (420-row) `adjudication.merge()` output --
    NOT just the 253 adjudicated ones -- because the two-stage estimator
    needs the true `n_agree` (all sampled agreements, most never
    individually adjudicated) to extrapolate the control slice's measured
    rate across them, exactly as `analyze.build_cell_estimates` does for
    the classifier. `verdicts`: raw `calibration_verdicts.json` content.
    `predictions_by_key`: `row["key"]` -> this predictor's guess (or None
    if it abstained / had no vector). Ground truth for a given adjudicated
    item is derived identically to `embed_data.load_labelled_items` --
    kept as an inline second implementation here (not imported) so a bug
    in one does not silently pass the other's test; both are exercised by
    `tests/calibration/test_embed_instrument.py`."""
    from collections import defaultdict

    from .stats import estimate_cell_accuracy

    def cell_key(row: dict) -> str:
        return f"{row['city']}:{row['facet']}:{round(row['confidence'], 2)}"

    by_cell: dict[str, list[dict]] = defaultdict(list)
    for row in merged_rows:
        by_cell[cell_key(row)].append(row)

    out = {}
    for cell, rows in by_cell.items():
        agree_rows = [r for r in rows if r["agree"]]
        disagree_rows = [r for r in rows if not r["agree"]]

        agree_adjudicated = 0
        agree_adjudicated_correct = 0
        for r in agree_rows:
            verdict = verdicts.get(r["key"] + ":control")
            if verdict is None:
                continue
            agree_adjudicated += 1
            # A control item's true value is its own proposed_value: the
            # classifier and LLM already agreed by construction, and every
            # control verdict in this dataset is "classifier" (i.e.
            # confirmed correct) -- there are zero "neither" control
            # verdicts (checked in embed_data.load_labelled_items).
            pred = predictions_by_key.get(r["key"])
            if verdict == "classifier" and pred is not None and pred == r["proposed_value"]:
                agree_adjudicated_correct += 1

        disagree_correct = 0
        for r in disagree_rows:
            verdict = verdicts.get(r["key"] + ":disagreement")
            if verdict is None:
                continue
            true_value = r["proposed_value"] if verdict == "classifier" else (
                r["llm_value"] if verdict == "llm" else None
            )
            if true_value is None:
                continue
            pred = predictions_by_key.get(r["key"])
            if pred is not None and pred == true_value:
                disagree_correct += 1

        out[cell] = estimate_cell_accuracy(
            cell=cell,
            n_total=population_by_cell.get(cell, len(rows)),
            n_sampled=len(rows),
            n_agree=len(agree_rows),
            n_disagree=len(disagree_rows),
            n_agree_adjudicated=agree_adjudicated,
            n_agree_adjudicated_correct=agree_adjudicated_correct,
            n_disagree_adjudicated_correct_for_classifier=disagree_correct,
        )
    return out
