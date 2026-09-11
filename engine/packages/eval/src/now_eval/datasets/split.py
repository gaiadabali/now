"""Deterministic hold-out split over the article corpus.

Every labelled set that could gate a *trainable* model (facet tagging /
E2.2, type classification / E2.1) is drawn exclusively from the `eval`
partition below. `train` is what E2.1/E2.2 are free to fit on,
featurize from, or use as few-shot examples — anything, as long as it
never informs a number this harness reports.

The split is a pure function of `wp_id` (stable across re-runs, no
random.seed() state to accidentally drift) salted so it does not
coincide with any other hash-based partitioning already used in the
pipeline. Changing SALT or EVAL_FRACTION changes every downstream
labelled set — bump SPLIT_VERSION if you do, and regenerate all
labelled sets together (`now-eval build-datasets`), never partially.
"""
from __future__ import annotations

import hashlib

SPLIT_VERSION = "now-eval-split-v1"
EVAL_FRACTION = 0.20


def split_bucket(wp_id: int, *, salt: str = SPLIT_VERSION) -> int:
    """Stable integer in [0, 100) for a given wp_id. Exposed separately
    from split_for() so callers needing a different fraction than the
    package default can still share one canonical assignment order
    (e.g. take the first 10% of buckets rather than a different hash)."""
    digest = hashlib.sha256(f"{salt}:{wp_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def split_for(wp_id: int, *, eval_fraction: float = EVAL_FRACTION, salt: str = SPLIT_VERSION) -> str:
    """'eval' or 'train' for one article id."""
    return "eval" if split_bucket(wp_id, salt=salt) < eval_fraction * 100 else "train"


def is_eval(wp_id: int, *, eval_fraction: float = EVAL_FRACTION, salt: str = SPLIT_VERSION) -> bool:
    return split_for(wp_id, eval_fraction=eval_fraction, salt=salt) == "eval"
