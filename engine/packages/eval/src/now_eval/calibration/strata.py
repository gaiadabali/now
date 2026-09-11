"""Stratified sampling design, pure logic over plain dicts/dataclasses so it
is unit-testable without a DB connection.

**Why strata are keyed by exact confidence VALUE, not by an arbitrary numeric
band:** `now_classifier.confidence` (F96) does not emit a continuous score.
It emits one of a handful of hand-picked constants (0.95/0.93/0.75/0.72/0.45/
0.40 for the type/format facets this package calibrates). A live query of
both cities' `classification_reviews` + `engine.entity_terms` confirms this:
zero rows carry any confidence value in the (0.75, 0.93) gap that straddles
the 0.85 gate. So "sample around the 0.85 boundary" cannot mean "sample
scores near 0.85" -- nothing scores near 0.85. It means: get enough evidence
on *each side* of the gate (0.75 and below vs. 0.93 and above) to tell
whether the two-sided split the invented mapping drew is actually where the
accuracy cliff is.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

# Target sample size per confidence-value cell, keyed by the exact value
# `now_classifier.confidence` currently assigns. Sizing rationale (see
# PROVENANCE.md §8 for the full writeup):
#   - 0.95 / 0.93 / 0.75 are the three values that most directly bear on the
#     gate decision -- 0.95+0.93 are what's currently auto-applied, and 0.75
#     is the value immediately below the gate with by far the largest
#     population, i.e. the biggest single lever on F97's queue size if it
#     turns out to be misfiled. n=25 gives a Wilson 95% CI half-width of
#     roughly +/-16pp at p=0.8 -- wide, but the tightest affordable given the
#     "a few hundred calls" budget spread across ~20 cells.
#   - 0.72 (cue fired, per-article, below its own "confident" margin) is
#     secondary evidence for the same per-article cue instrument that
#     produces 0.93 -- n=15.
#   - 0.45 / 0.40 are the two lowest, least gate-relevant values (a human
#     "low" category guess, or the cue abstaining entirely) -- n=12, enough
#     to confirm they really are as unreliable as the mapping assumes
#     without spending budget on the least decision-relevant cells.
#   - 0.70 / 0.35 are `subtype`'s own two mechanisms (added by the subtype
#     calibration ticket -- see `subtype.py`), distinct numbers from any
#     type/format value so adding them here cannot change type/format's
#     existing sampling at all. 0.70 (`SUBTYPE_KEYWORD_MATCH`, source="ai")
#     is subtype's newest, least-evidenced instrument (E2.1's own keyword
#     matcher, "kept deliberately conservative") and its single largest
#     review-queue population in both cities combined (~1,941 rows) -- it
#     gets the biggest n of any subtype cell for the same reason 0.75 got
#     the biggest n in `location.py`. 0.35 (`SUBTYPE_NO_MATCH_FALLBACK`,
#     source="inferred") is the least decision-relevant subtype value (an
#     abstain-and-fall-back-further case) -- small n just to confirm it
#     really is as unreliable as the mapping assumes.
TARGET_N_BY_CONFIDENCE: dict[float, int] = {
    0.95: 25,
    0.93: 25,
    0.75: 25,
    0.72: 15,
    0.45: 12,
    0.40: 12,
    0.70: 35,
    0.35: 15,
}
DEFAULT_TARGET_N = 15  # any confidence value not in the table above (future-proofing)


def target_n(confidence: float, population: int) -> int:
    """Sample size for one (city, facet, confidence-value) cell, capped at
    the cell's actual population (never oversample a small cell)."""
    key = round(float(confidence), 2)
    n = TARGET_N_BY_CONFIDENCE.get(key, DEFAULT_TARGET_N)
    return min(n, population)


def _stable_rank(seed: str, key: str) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


@dataclass(frozen=True)
class FrameRecord:
    """One (article, facet) sampling unit. `key` must uniquely identify the
    record for deterministic hashing (e.g. f"{city}:{wp_id}:{facet}")."""
    key: str
    city: str
    facet: str
    proposed_value: str
    confidence: float


def stratified_sample(
    records: list[FrameRecord],
    *,
    seed: str = "now-eval-calibration-v1",
) -> list[FrameRecord]:
    """Groups by (city, facet, confidence), samples `target_n` per group,
    and within a group spreads picks across distinct `proposed_value`s
    round-robin rather than taking whatever a plain random draw happens to
    surface -- a cell dominated by one value (e.g. `type=eat` at confidence
    0.95, since `eat` is the single largest category in the corpus) would
    otherwise tell us almost nothing about the other 8 type values sharing
    that same confidence number.

    Deterministic: a seeded hash of `key` both ranks candidates within a
    value-group (for reproducible "randomness") and the round-robin order
    over value-groups is sorted by value name, so re-running against
    unchanged input reproduces the same sample.
    """
    by_cell: dict[tuple[str, str, float], dict[str, list[FrameRecord]]] = {}
    for r in records:
        cell = (r.city, r.facet, round(r.confidence, 2))
        by_cell.setdefault(cell, {}).setdefault(r.proposed_value, []).append(r)

    selected: list[FrameRecord] = []
    for cell, by_value in by_cell.items():
        population = sum(len(v) for v in by_value.values())
        n = target_n(cell[2], population)
        # Rank within each value group deterministically, independent of
        # input order.
        ranked = {
            value: sorted(items, key=lambda r: _stable_rank(seed, r.key))
            for value, items in by_value.items()
        }
        cursors = {value: 0 for value in ranked}
        value_order = sorted(ranked.keys(), key=lambda v: _stable_rank(seed, f"cell-order:{cell}:{v}"))
        picked = 0
        while picked < n:
            progressed = False
            for value in value_order:
                if picked >= n:
                    break
                idx = cursors[value]
                if idx < len(ranked[value]):
                    selected.append(ranked[value][idx])
                    cursors[value] = idx + 1
                    picked += 1
                    progressed = True
            if not progressed:
                break  # every value group exhausted before reaching n (n was capped at population, so this is just a safety net)
    return selected
