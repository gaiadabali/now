"""Internal-consistency check: does a category hold one kind of thing?

For every category with enough members we compute, in the city's vector
space (real embeddings for Jakarta, TF-IDF/LSA proxy for Bali):

* `cohesion`        mean cosine of members to their own centroid, reported
                    against the corpus-wide baseline (random sets of the
                    same size) as a z-like ratio, so 0.55 means something
                    different in a 384-dim embedding space than in LSA.
* `leakage`         share of members whose nearest *other* category centroid
                    is closer than their own -- "this article would be
                    filed elsewhere by a nearest-centroid classifier". The
                    categories it leaks into are listed ("confusable_with").
* `split`           k-means with k=2 and k=3; the best silhouette, the
                    cluster shares, and for each cluster its dominant cue
                    type/format, top title words and the titles nearest its
                    centroid -- so a real split is visible on sight.

The verdict combines them with what the *proposal* claims: a category whose
proposal already says "type per article" (News, Events) is *expected* to be
heterogeneous, and is labelled so rather than flagged; a category whose
proposal asserts one type/format but whose clusters carry different cue
types/formats is an `incoherent` -- a split candidate, not a mapping problem.
"""
from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from .sources import Article
from .text import DECAY_CLASS, VENUE_TYPES, tokens
from .vectors import VectorSpace

MIN_MEMBERS = 8


@dataclass
class ClusterView:
    size: int
    share: float
    top_type: str | None
    top_type_share: float
    top_format: str | None
    top_format_share: float
    top_words: list[str]
    examples: list[dict]  # {wp_id, title, date}


@dataclass
class Coherence:
    n: int
    vector_source: str
    is_proxy: bool
    cohesion: float
    baseline: float
    cohesion_ratio: float
    leakage: float
    leakage_cross_type: float
    confusable_with: list[tuple[str, int]]
    best_k: int | None
    silhouette: float | None
    clusters: list[ClusterView] = field(default_factory=list)
    verdict: str = "n/a"           # coherent | mixed | incoherent | expected-heterogeneous | too-small
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "n": self.n, "vector_source": self.vector_source, "is_proxy": self.is_proxy,
            "cohesion": round(self.cohesion, 3), "baseline": round(self.baseline, 3), "cohesion_ratio": round(self.cohesion_ratio, 2),
            "leakage": round(self.leakage, 3), "leakage_cross_type": round(self.leakage_cross_type, 3), "confusable_with": [{"category": c, "articles": k} for c, k in self.confusable_with],
            "best_k": self.best_k, "silhouette": None if self.silhouette is None else round(self.silhouette, 3),
            "clusters": [
                {"size": c.size, "share": round(c.share, 2), "top_type": c.top_type, "top_type_share": round(c.top_type_share, 2),
                 "top_format": c.top_format, "top_format_share": round(c.top_format_share, 2), "top_words": c.top_words, "examples": c.examples}
                for c in self.clusters
            ],
            "verdict": self.verdict, "reason": self.reason,
        }


def _kmeans(X: np.ndarray, k: int, seed: int = 0) -> tuple[np.ndarray, float]:
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
        km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(X)
        labels = km.labels_
        if len(set(labels)) < 2:
            return labels, -1.0
        return labels, float(silhouette_score(X, labels, metric="cosine"))
    except ImportError:
        return _numpy_kmeans(X, k, seed)


def _numpy_kmeans(X: np.ndarray, k: int, seed: int) -> tuple[np.ndarray, float]:
    rng = np.random.RandomState(seed)
    n = X.shape[0]
    centers = X[rng.choice(n, 1)]
    for _ in range(1, k):  # k-means++ seeding
        d = 1 - X @ centers.T
        dmin = d.min(axis=1)
        p = dmin / dmin.sum() if dmin.sum() > 0 else np.full(n, 1 / n)
        centers = np.vstack([centers, X[rng.choice(n, 1, p=p)]])
    labels = np.zeros(n, dtype=int)
    for _ in range(50):
        sims = X @ centers.T
        new = sims.argmax(axis=1)
        if (new == labels).all():
            break
        labels = new
        for j in range(k):
            m = X[labels == j]
            if len(m):
                c = m.mean(axis=0)
                centers[j] = c / (np.linalg.norm(c) or 1)
    # cosine silhouette
    D = 1 - X @ X.T
    s = []
    for i in range(n):
        own = labels[i]
        a = D[i, labels == own]
        a = a[a > 0].mean() if (labels == own).sum() > 1 else 0.0
        b = min(D[i, labels == j].mean() for j in range(k) if j != own and (labels == j).any())
        s.append((b - a) / max(a, b) if max(a, b) > 0 else 0.0)
    return labels, float(np.mean(s))


def _top_words(titles: list[str], k: int = 6) -> list[str]:
    c: Counter[str] = Counter()
    for t in titles:
        c.update(set(tokens(t)))
    return [w for w, _ in c.most_common(k)]


def _share(counter: Counter, exclude_none: bool = True) -> tuple[str | None, float]:
    items = [(k, v) for k, v in counter.items() if not (exclude_none and k is None)]
    total = sum(v for _, v in items)
    if not total:
        return None, 0.0
    k, v = max(items, key=lambda kv: kv[1])
    return k, v / total


def analyse_category(
    name: str,
    members: list[Article],
    space: VectorSpace,
    all_centroids: dict[str, np.ndarray],
    features: dict[int, dict],
    baseline_by_n: dict[int, float],
    expected_heterogeneous: bool,
    claimed_type: str | None,
    claimed_format: str | None,
    rng: random.Random,
    fixed_type_of: dict[str, str | None] | None = None,
) -> Coherence:
    fixed_type_of = fixed_type_of or {}
    idx = space.index()
    rows = [idx[a.wp_id] for a in members if a.wp_id in idx]
    arts = [a for a in members if a.wp_id in idx]
    n = len(rows)
    if n < MIN_MEMBERS:
        return Coherence(n, space.source, space.is_proxy, 0, 0, 0, 0, 0, [], None, None, [], "too-small", f"{n} members with vectors (< {MIN_MEMBERS}); read the titles instead")
    X = space.matrix[rows]
    centroid = X.mean(axis=0)
    centroid /= np.linalg.norm(centroid) or 1
    cohesion = float((X @ centroid).mean())
    baseline = baseline_by_n.get(min(n, max(baseline_by_n)), 0.0)
    ratio = cohesion / baseline if baseline else 0.0

    # leakage against every other category's centroid
    others = {k: v for k, v in all_centroids.items() if k != name}
    leak = Counter()
    cross = 0
    if others:
        names = list(others)
        C = np.vstack([others[k] for k in names])
        sims = X @ C.T
        own = X @ centroid
        best = sims.argmax(axis=1)
        for i in range(n):
            if sims[i, best[i]] > own[i]:
                nb = names[best[i]]
                leak[nb] += 1
                # leakage into a category whose *fixed* type differs from ours is
                # the kind that matters for exclusion; siblings sharing our type are not
                other_t = fixed_type_of.get(nb)
                if claimed_type and other_t and other_t != claimed_type:
                    cross += 1
    leakage = sum(leak.values()) / n
    leakage_cross = cross / n

    # split analysis
    best_k, best_sil, best_labels = None, None, None
    for k in (2, 3):
        if n < 4 * k:
            continue
        labels, sil = _kmeans(X, k)
        if best_sil is None or sil > best_sil:
            best_k, best_sil, best_labels = k, sil, labels
    clusters: list[ClusterView] = []
    if best_labels is not None:
        for j in range(best_k):
            mem = [i for i in range(n) if best_labels[i] == j]
            if not mem:
                continue
            sub = X[mem]
            c = sub.mean(axis=0)
            c /= np.linalg.norm(c) or 1
            order = np.argsort(-(sub @ c))
            ex = [arts[mem[o]] for o in order[:4]]
            ty = Counter(features.get(arts[i].wp_id, {}).get("type") for i in mem)
            fo = Counter(features.get(arts[i].wp_id, {}).get("format") for i in mem)
            tt, ts = _share(ty)
            ft, fs = _share(fo)
            clusters.append(ClusterView(len(mem), len(mem) / n, tt, ts, ft, fs, _top_words([arts[i].title for i in mem]),
                                        [{"wp_id": a.wp_id, "title": a.title, "date": a.date[:10]} for a in ex]))
        clusters.sort(key=lambda c: -c.size)

    # verdict
    verdict, reason = "coherent", ""
    minority = min((c.share for c in clusters), default=0.0)
    confident = [c for c in clusters if c.top_type and c.top_type_share >= 0.45]
    types_seen = {c.top_type for c in confident}
    distinct_type = len(types_seen) > 1
    # a type split matters when it crosses into (or between) venue types -- that is
    # what competitor exclusion keys on; editorial<->do<->event splits do not exclude anything
    venue_split = distinct_type and any(t in VENUE_TYPES for t in types_seen)
    fmt_classes = {DECAY_CLASS.get(c.top_format) for c in clusters if c.top_format and c.top_format_share >= 0.45}
    distinct_format = len(fmt_classes) > 1  # different decay classes, not merely different labels
    strong_split = best_sil is not None and best_sil >= (0.08 if not space.is_proxy else 0.05) and minority >= 0.2
    if expected_heterogeneous:
        verdict = "expected-heterogeneous"
        reason = "the proposal already leaves type per article (or this is a container / print issue); heterogeneity is by design"
        if strong_split and (distinct_type or distinct_format):
            reason += f"; k={best_k} clusters carry different cue types/formats -- useful as classifier priors, not a mapping problem"
    elif strong_split and venue_split and claimed_type:
        verdict = "incoherent"
        reason = f"k={best_k} split (silhouette {best_sil:.2f}, smallest cluster {minority:.0%}) whose clusters read as different venue types ({', '.join(sorted(t for t in types_seen if t))}) while the proposal fixes type={claimed_type}; {leakage_cross:.0%} of members sit closer to a category of another type"
    elif strong_split and distinct_format and claimed_format:
        verdict = "incoherent"
        reason = f"k={best_k} split (silhouette {best_sil:.2f}, smallest cluster {minority:.0%}) whose clusters read as formats with different decay ({', '.join(sorted(c for c in fmt_classes if c))}) while the proposal fixes format={claimed_format}"
    elif strong_split and (distinct_type or distinct_format):
        verdict = "mixed"
        what = " and ".join(x for x, ok in (("type", distinct_type), ("decay class", distinct_format)) if ok)
        reason = f"k={best_k} split (silhouette {best_sil:.2f}) with clusters disagreeing on {what}; cross-type leakage {leakage_cross:.0%}"
    elif claimed_type and leakage_cross >= 0.3:
        verdict = "mixed"
        reason = f"{leakage_cross:.0%} of members sit closer to a category of a different type ({', '.join(f'{c} {k}' for c, k in leak.most_common(3))})"
    elif ratio < 1.0:
        verdict = "mixed"
        reason = f"cohesion {cohesion:.2f} is no higher than the random baseline {baseline:.2f} for a set this size"
    else:
        reason = f"cohesion {cohesion:.2f} vs baseline {baseline:.2f}; leakage {leakage:.0%} (cross-type {leakage_cross:.0%})"
    return Coherence(n, space.source, space.is_proxy, cohesion, baseline, ratio, leakage, leakage_cross, leak.most_common(4), best_k, best_sil, clusters, verdict, reason)


def baseline_curve(space: VectorSpace, sizes: tuple[int, ...] = (8, 12, 20, 35, 60, 100, 200, 400, 800, 1200), draws: int = 25, seed: int = 0) -> dict[int, float]:
    """Mean cosine-to-centroid of random article sets, per size: what a
    category made of unrelated pieces would score in this space."""
    rng = np.random.RandomState(seed)
    n = space.matrix.shape[0]
    out: dict[int, float] = {}
    for s in sizes:
        if s > n:
            break
        vals = []
        for _ in range(draws):
            rows = rng.choice(n, s, replace=False)
            X = space.matrix[rows]
            c = X.mean(axis=0)
            c /= np.linalg.norm(c) or 1
            vals.append(float((X @ c).mean()))
        out[s] = float(np.mean(vals))
    return out


def baseline_for(n: int, curve: dict[int, float]) -> float:
    if not curve:
        return 0.0
    ks = sorted(curve)
    if n <= ks[0]:
        return curve[ks[0]]
    if n >= ks[-1]:
        return curve[ks[-1]]
    for lo, hi in zip(ks, ks[1:]):
        if lo <= n <= hi:
            t = (math.log(n) - math.log(lo)) / (math.log(hi) - math.log(lo))
            return curve[lo] + t * (curve[hi] - curve[lo])
    return curve[ks[-1]]


def category_centroids(space: VectorSpace, members_by_cat: dict[str, list[Article]], min_members: int = MIN_MEMBERS) -> dict[str, np.ndarray]:
    idx = space.index()
    out: dict[str, np.ndarray] = {}
    for name, members in members_by_cat.items():
        rows = [idx[a.wp_id] for a in members if a.wp_id in idx]
        if len(rows) < min_members:
            continue
        c = space.matrix[rows].mean(axis=0)
        out[name] = c / (np.linalg.norm(c) or 1)
    return out
