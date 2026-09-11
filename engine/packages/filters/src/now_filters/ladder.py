"""Fallback ladder (ARCHITECTURE.md Sec.8.F): "Every rail must fill.
Evaluate rungs until slot count is met; record the rung reached." and
Sec.1 principle 6 / Sec.8.F's closing sentence: **"The competitor filter
never relaxes at any rung."**

This module owns two responsibilities:

1. **Orchestration** -- walk `DEFAULT_LADDER` (or a caller-supplied rung
   sequence), calling a rail-specific `fetch_fn(rung) -> list[Candidate]`
   at each rung until `slots_needed` candidates are found or the ladder is
   exhausted, and recording which rung was reached (`RungResult`,
   retrievable by the Inspector per ARCHITECTURE.md Sec.17).

2. **Enforcement, not just trust** -- `fetch_fn` is owned by whichever
   rail calls this (Row 1/2/3, E3.3/E3.5-3.7), not by this package. Per
   the task brief's own instruction ("prove... survives every fallback
   rung"), this module does not simply assume every rail implementation
   correctly re-applies `hard.py`'s competitor predicate at every rung --
   it re-derives the excluded-type set from `engine.type_relations` itself
   and drops any competitor that slipped through, at every single rung,
   unconditionally. A rail's `fetch_fn` that forgot the exclusion
   entirely would still produce a competitor-clean `RungResult` here; it
   would just (correctly) look like it under-filled and fall through to
   the next rung, which is the intended fail-safe behaviour for a
   commercial guarantee this important.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from now_filters.models import DEFAULT_LADDER, Candidate, RungResult, RungSpec
from now_filters.type_relations import TypeRelation, excluded_types_for

FetchFn = Callable[[RungSpec], list[Candidate]]


@dataclass(frozen=True)
class LadderRun:
    result: RungResult
    rungs_evaluated: list[str]


def _enforce_competitor_invariant(
    candidates: list[Candidate], relations: dict[str, TypeRelation], subject_type: str | None
) -> list[Candidate]:
    """F73/F74 (PROGRESS.md): this was a THIRD place the same disagreement
    lived, alongside `hard.py`'s SQL and `type_relations.is_competitor` --
    `c.type not in excluded` is a plain Python `in`-check, and `None not in
    {"stay", ...}` is `True`, so a `Candidate` with `type=None` (an
    unclassified article, F50) survived this defensive re-check even when
    `excluded` was non-empty, silently disagreeing with the SQL stage that
    is supposed to have already removed it. Fixed to the same fail-closed
    rule `is_competitor` documents: when the subject excludes anything at
    all, a candidate whose type we cannot identify cannot be vouched for
    as safe, so it is dropped here too rather than passed through on a
    technicality of `in` against `None`."""
    excluded = excluded_types_for(relations, subject_type)
    if not excluded:
        return candidates
    return [c for c in candidates if c.type is not None and c.type not in excluded]


def _enforce_status_invariant(candidates: list[Candidate]) -> list[Candidate]:
    """F27's second unconditional guarantee, re-checked defensively at
    the ladder level for the same reason as the competitor invariant
    above: a place whose `status` is populated and is anything other than
    `active` must never reach a rung's result, no matter what `fetch_fn`
    returned. Candidates with `status=None` (e.g. articles, which have no
    place-style status field on this Candidate shape) are not place rows
    and are left alone -- this check only fires for entities that report
    a status at all."""
    return [c for c in candidates if c.status is None or c.status == "active"]


def run_ladder(
    fetch_fn: FetchFn,
    *,
    subject_type: str | None,
    relations: dict[str, TypeRelation],
    slots_needed: int,
    ladder: tuple[RungSpec, ...] = DEFAULT_LADDER,
) -> LadderRun:
    rungs_evaluated: list[str] = []
    last_result: list[Candidate] = []
    last_rung_index = 0
    last_rung_name = ladder[0].name if ladder else "strict"

    for idx, rung in enumerate(ladder):
        rungs_evaluated.append(rung.name)
        raw = fetch_fn(rung)
        safe = _enforce_competitor_invariant(raw, relations, subject_type)
        safe = _enforce_status_invariant(safe)
        last_result, last_rung_index, last_rung_name = safe, idx, rung.name
        if len(safe) >= slots_needed:
            break

    return LadderRun(
        result=RungResult(
            candidates=last_result[:slots_needed] if len(last_result) >= slots_needed else last_result,
            rung_index=last_rung_index,
            rung_name=last_rung_name,
            slots_requested=slots_needed,
        ),
        rungs_evaluated=rungs_evaluated,
    )
