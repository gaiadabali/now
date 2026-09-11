"""Dedup clustering for candidate venue names that had NO gazetteer hit
(i.e. genuinely new-to-the-city, not yet a `public.places` row).

Union-find over pairwise similarity, gated at the project's own stated
confidence convention (`rules.confidence_gate`, `<city>/site/
taxonomy-review.json`): score >= AUTO_MERGE_THRESHOLD (0.85) merges
automatically; below it, pairs are recorded as review candidates and
left UNMERGED (precision bias -- "prefer precision; route uncertain
merges to review rather than guessing"). A pair scoring below
REVIEW_FLOOR is not related at all and is not surfaced anywhere -- most
name pairs in a large corpus share nothing and would otherwise flood the
review queue with noise.

Only compares within the same blocking key (see normalize.blocking_key)
-- this is what keeps the whole thing well under O(n^2) for a
several-hundred-candidate city.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from now_place_extraction.match import SimilarityResult, similarity
from now_place_extraction.normalize import blocking_key

AUTO_MERGE_THRESHOLD = 0.85
REVIEW_FLOOR = 0.55


@dataclass
class ReviewPair:
    name_a: str
    name_b: str
    result: SimilarityResult


@dataclass
class Cluster:
    canonical_name: str
    members: list[str] = field(default_factory=list)
    mention_count: int = 0


class _UnionFind:
    def __init__(self, items: list[str]):
        self._parent = {item: item for item in items}

    def find(self, x: str) -> str:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra


@dataclass
class DedupResult:
    clusters: list[Cluster]
    review_pairs: list[ReviewPair]


def cluster_candidates(
    surface_counts: dict[str, int],
    *,
    auto_merge_threshold: float = AUTO_MERGE_THRESHOLD,
    review_floor: float = REVIEW_FLOOR,
    llm_adjudicate: "callable | None" = None,
) -> DedupResult:
    """`surface_counts`: distinct surface_text -> number of mentions found
    across the corpus (case/whitespace-normalized already by the caller).

    `llm_adjudicate`, if given, is called ONLY on pairs whose deterministic
    score falls strictly between `review_floor` and `auto_merge_threshold`
    (the genuinely ambiguous band) as `llm_adjudicate(name_a, name_b) ->
    bool | None` (None = "couldn't decide, treat as review"). Budget
    enforcement (call cap, usage logging) lives in the caller
    (llm.py/pipeline.py), not here -- this function has no idea what a
    "call" costs.
    """
    names = list(surface_counts.keys())
    by_block: dict[str, list[str]] = defaultdict(list)
    for n in names:
        by_block[blocking_key(n)].append(n)

    uf = _UnionFind(names)
    review_pairs: list[ReviewPair] = []

    for _block, group in by_block.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                result = similarity(a, b)
                if result.score >= auto_merge_threshold:
                    uf.union(a, b)
                elif result.score >= review_floor:
                    decided = llm_adjudicate(a, b) if llm_adjudicate else None
                    if decided is True:
                        uf.union(a, b)
                    else:
                        review_pairs.append(ReviewPair(name_a=a, name_b=b, result=result))

    groups: dict[str, list[str]] = defaultdict(list)
    for n in names:
        groups[uf.find(n)].append(n)

    clusters: list[Cluster] = []
    for members in groups.values():
        # Canonical surface form: the most frequently occurring exact
        # surface text in the cluster (ties broken by longest, then
        # alphabetically, for determinism across re-runs).
        canonical = max(members, key=lambda m: (surface_counts[m], len(m), m))
        clusters.append(
            Cluster(
                canonical_name=canonical,
                members=sorted(members),
                mention_count=sum(surface_counts[m] for m in members),
            )
        )
    clusters.sort(key=lambda c: (-c.mention_count, c.canonical_name))
    return DedupResult(clusters=clusters, review_pairs=review_pairs)
