"""Similarity scoring between two venue-name candidates.

Deliberately conservative: three signals are combined and the LOWEST of
them gates the final score, not the highest or an average. A false HIGH
merge is the commercially expensive failure mode this ticket calls out
("merging two distinct venues corrupts partner attribution and
competitor exclusion") so every signal must agree, not just one.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from now_place_extraction.normalize import core_tokens, normalize_full, tokens


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _seq_ratio(a: str, b: str) -> float:
    return SequenceMatcher(a=a, b=b).ratio()


@dataclass(frozen=True)
class SimilarityResult:
    score: float
    exact: bool
    full_ratio: float
    core_jaccard: float
    token_ratio: float


def similarity(name_a: str, name_b: str) -> SimilarityResult:
    full_a, full_b = normalize_full(name_a), normalize_full(name_b)
    if full_a and full_a == full_b:
        return SimilarityResult(score=1.0, exact=True, full_ratio=1.0, core_jaccard=1.0, token_ratio=1.0)

    core_a, core_b = set(core_tokens(name_a)), set(core_tokens(name_b))
    tok_a, tok_b = " ".join(sorted(tokens(name_a))), " ".join(sorted(tokens(name_b)))

    full_ratio = _seq_ratio(full_a, full_b)
    core_jaccard = _jaccard(core_a, core_b)
    token_ratio = _seq_ratio(tok_a, tok_b)

    # `core_jaccard` is the PRIMARY signal, not one vote among equals: it
    # operates on the discriminating tokens only (generic venue/geo words
    # already stripped), which is exactly what distinguishes "same venue,
    # dropped/added a suffix word" from "different venue, coincidentally
    # similar-looking string". When the discriminating token sets are
    # IDENTICAL (core_jaccard == 1.0), that alone is strong enough
    # evidence to clear the auto-merge gate -- "The Ritz-Carlton Jakarta
    # Mega Kuningan" vs "Ritz Carlton Mega Kuningan" differ only in
    # generic words ("The", "Jakarta"), and `full_ratio` alone would
    # under-score that pair for a reason that has nothing to do with
    # whether it's the same venue (it is). `full_ratio` still nudges the
    # score toward 1.0 for near-identical strings, but a 1.0 core_jaccard
    # can never be dragged below the auto-merge floor by it.
    #
    # When the core sets are NOT identical, core_jaccard dominates the
    # blend (weight 0.7) -- this is what correctly keeps "Padma Resort
    # Ubud" (core {padma, ubud}) and "Padma Resort Legian" (core {padma,
    # legian}) apart despite a very high `full_ratio` (the two strings
    # differ by one word): jaccard = 1/3 pulls the blended score well
    # under the gate even though the raw strings look 85%+ similar.
    shared_core = core_a & core_b
    if core_a and core_b and len(shared_core) >= 2:
        # `core_jaccard` only gets to DOMINATE the blend when at least TWO
        # distinguishing tokens actually agree -- one shared word is too
        # cheap a coincidence to trust heavily, especially when that word
        # is a common descriptor rather than a real brand/place word.
        # "The Ritz-Carlton Jakarta Mega Kuningan" vs "Ritz Carlton Mega
        # Kuningan" shares FOUR tokens ({ritz, carlton, mega, kuningan})
        # after stripping "The"/"Jakarta" -- strong evidence, floor 0.90.
        if core_jaccard == 1.0:
            score = max(0.90, full_ratio)
        else:
            score = 0.7 * core_jaccard + 0.3 * full_ratio
    elif core_a and core_b:
        # 0 or 1 shared distinguishing token: NOT enough independent
        # evidence to let jaccard drive the score, so the weighting
        # inverts -- whole-string closeness (full_ratio) now dominates,
        # and jaccard only nudges it. Found live: "Grand Suite" and
        # "Grand Club" both reduce to the single core token {"grand"}
        # once "suite"/"club" are stripped as generic (jaccard == 1.0 on
        # a set of size 1) -- the old rule gave this the SAME 0.90+ floor
        # as the four-token Ritz-Carlton case, which is not comparable
        # evidence, and merged a room-type name, a membership-tier name,
        # and an unrelated hotel ("The Grand Bali Beach") into one cluster.
        score = 0.3 * core_jaccard + 0.7 * full_ratio
    else:
        score = min(full_ratio, token_ratio)
    return SimilarityResult(score=score, exact=False, full_ratio=full_ratio, core_jaccard=core_jaccard, token_ratio=token_ratio)
