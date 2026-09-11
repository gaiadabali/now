"""Pluggable system-under-test (SUT) interface.

The systems this harness measures (E2.1 classifier, E3.1 search,
E3.5-3.7 rails) do not exist yet. Every gate is defined against this
Protocol so the harness itself, its datasets, and its metrics can be
built, tested, and CI-gated today; the day a real classifier or search
ranker exists, it is wired in by implementing this interface -- no
harness code changes.

`TrivialRandomSUT` and `TrivialMostPopularSUT` are the two baselines the
task asks for, used to (a) prove the metrics actually discriminate
(a real system should beat both) and (b) establish the first recorded,
dated baseline so later work has something concrete to regress against.
"""
from __future__ import annotations

import hashlib
import random
from collections import Counter
from typing import Protocol


class SystemUnderTest(Protocol):
    """Everything a candidate ranking/classification system must
    implement to be pluggable into this harness."""

    def related(self, article_id: str, candidate_ids: list[str], k: int) -> list[str]:
        """Return up to k candidate_ids, best match first, for
        "articles related to article_id". candidate_ids never includes
        article_id itself."""
        ...

    def rank(self, query: str, candidate_ids: list[str], k: int) -> list[str]:
        """Return up to k candidate_ids, best match first, for `query`."""
        ...

    def tag_facets(self, article_id: str) -> set[str]:
        """Return the set of facet-slug tags this system would apply to
        article_id."""
        ...

    def classify_type(self, article_id: str) -> str:
        """Return the single predicted L1 `type` for article_id."""
        ...


class TrivialRandomSUT:
    """Pure noise, seeded for reproducibility. The floor every real
    system must clear -- if a real system doesn't beat this by a wide
    margin, something in the pipeline (not the eval harness) is broken.
    """

    def __init__(self, seed: int = 0, known_types: tuple[str, ...] = ("stay", "eat", "drink", "do", "wellness", "shop", "event", "editorial")) -> None:
        self._seed = seed
        self._known_types = known_types

    def _rng_for(self, *parts: str) -> random.Random:
        digest = hashlib.sha256(f"{self._seed}:{':'.join(parts)}".encode()).hexdigest()
        return random.Random(int(digest[:16], 16))

    def related(self, article_id: str, candidate_ids: list[str], k: int) -> list[str]:
        rng = self._rng_for("related", article_id)
        pool = list(candidate_ids)
        rng.shuffle(pool)
        return pool[:k]

    def rank(self, query: str, candidate_ids: list[str], k: int) -> list[str]:
        rng = self._rng_for("rank", query)
        pool = list(candidate_ids)
        rng.shuffle(pool)
        return pool[:k]

    def tag_facets(self, article_id: str) -> set[str]:
        rng = self._rng_for("facets", article_id)
        # A random single-word-ish slug -- essentially never matches a
        # real held-out label, which is the point (precision/recall
        # near 0 proves the metric discriminates against noise).
        return {f"random-{rng.randint(0, 999999)}"}

    def classify_type(self, article_id: str) -> str:
        rng = self._rng_for("type", article_id)
        return rng.choice(self._known_types)


class TrivialMostPopularSUT:
    """Always returns the single most frequent answer, ignoring the
    query/article entirely. Fit once via `.fit(...)` on the *train*
    split labels (never eval-split labels -- see datasets/split.py) so
    this baseline itself respects the hold-out contract it exists to
    validate.
    """

    def __init__(self) -> None:
        self._most_common_type: str | None = None
        self._popular_order: list[str] = []

    def fit_type(self, train_type_labels: dict[str, str]) -> "TrivialMostPopularSUT":
        if not train_type_labels:
            raise ValueError("cannot fit on an empty label set")
        counts = Counter(train_type_labels.values())
        self._most_common_type = counts.most_common(1)[0][0]
        return self

    def fit_popularity_order(self, ordered_article_ids_most_popular_first: list[str]) -> "TrivialMostPopularSUT":
        self._popular_order = list(ordered_article_ids_most_popular_first)
        return self

    def related(self, article_id: str, candidate_ids: list[str], k: int) -> list[str]:
        candidates = set(candidate_ids)
        ordered = [aid for aid in self._popular_order if aid in candidates]
        if len(ordered) < k:
            # Anything not in the fitted popularity order falls back to
            # input order rather than being silently dropped. Compute
            # the "already placed" set once (not per list-comprehension
            # element -- a `... if x not in set(ordered)` filter would
            # rebuild that set on every iteration, making this O(n^2)
            # over a multi-thousand-article corpus).
            already = set(ordered)
            ordered += [aid for aid in candidate_ids if aid not in already]
        return ordered[:k]

    def rank(self, query: str, candidate_ids: list[str], k: int) -> list[str]:
        return self.related("", candidate_ids, k)

    def tag_facets(self, article_id: str) -> set[str]:
        return set()  # "most popular facet" is underspecified for a multi-label set; abstain.

    def classify_type(self, article_id: str) -> str:
        if self._most_common_type is None:
            raise RuntimeError("call fit_type() with train-split labels before classify_type()")
        return self._most_common_type
