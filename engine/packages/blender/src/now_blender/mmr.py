"""Wires this package's real blend scores + real embedding similarity
into `now_filters.diversity.diversify` -- the MMR implementation itself
is NOT reimplemented here (it already exists, is tested, and correctly
enforces the org/area/format/paid caps inside the greedy loop per
ARCHITECTURE.md Sec.8.D; re-implementing it in this package would be the
"second hardcoded constant" anti-pattern this monorepo's other packages
explicitly avoid, e.g. `now_filters.hard`'s QUALITY_FLOOR import). This
module supplies the two things `diversify()` asks a caller for:

1. `relevance` -- this package's `compute_blend(...).normalized_score`
   per candidate (§7's score, minus diversity_penalty, which is exactly
   what MMR's own `lambda*relevance - (1-lambda)*max_sim` computes for
   the "minus diversity_penalty" term -- see `blend.py`'s docstring for
   why this is not double-subtracted).
2. `similarity_fn` -- `now_blender.similarity.build_similarity_fn`'s real
   cosine closure, replacing `now_filters.diversity.
   default_facet_similarity` (the "zero-dependency MMR stand-in
   explicitly waiting for a real cosine-similarity closure" the task
   brief names directly).

`lambda_=0.7` matches ARCHITECTURE.md Sec.8.D ("MMR lambda ~= 0.7")
and is the default here too, but is a parameter -- not a second
hardcoded 0.7 that could drift from `now_filters.diversity.
DEFAULT_LAMBDA` -- imported from that module instead of re-declared.
"""

from __future__ import annotations

from now_filters.diversity import DEFAULT_LAMBDA, DiversityCaps, SimilarityFn, diversify
from now_filters.models import Candidate


def diversify_ranked(
    candidates: list[Candidate],
    relevance: dict[tuple[str, int], float],
    *,
    k: int,
    similarity_fn: SimilarityFn,
    lambda_: float = DEFAULT_LAMBDA,
    caps: DiversityCaps | None = None,
) -> list[Candidate]:
    return diversify(candidates, relevance, k=k, similarity_fn=similarity_fn, lambda_=lambda_, caps=caps)
