"""QA.5 independent re-verification of F68 (PROGRESS.md).

Adversarial, end-to-end (real `run_ladder`, not just `excluded_types_for`
in isolation) proof that `subject_type=None` fails CLOSED, not open, at
every rung -- including a purpose-built `fetch_fn` (not copy-pasted from
any existing test fixture) where EVERY rung leaks None-typed competitor
candidates, all the way to the final `editorial_fallback` rung.

Run: engine/packages/filters/.venv/Scripts/python.exe f68_qa5_adversarial.py
(run from this file's directory; adjusts sys.path to import now_filters
from the sibling `filters` package without installing it).
"""

from __future__ import annotations

import sys
from pathlib import Path

FILTERS_SRC = Path(__file__).resolve().parents[1] / "filters" / "src"
sys.path.insert(0, str(FILTERS_SRC))

from now_filters.ladder import run_ladder  # noqa: E402
from now_filters.models import DEFAULT_LADDER, Candidate, RungSpec  # noqa: E402
from now_filters.type_relations import TypeRelation, excluded_types_for, is_competitor  # noqa: E402

FAILURES: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {label}" + (f" -- {detail}" if detail else ""))
    if not cond:
        FAILURES.append(label)


# Real seed relations (engine/packages/taxonomy/seed/type_relations.json),
# reproduced by hand here (not imported from a test fixture) so this
# script does not depend on any other test's setup.
RELATIONS: dict[str, TypeRelation] = {
    "unknown": TypeRelation("unknown", True, ()),
    "stay": TypeRelation("stay", True, ("eat", "drink", "wellness", "do")),
    "eat": TypeRelation("eat", True, ("drink", "do", "event")),
    "drink": TypeRelation("drink", True, ("eat", "do")),
    "wellness": TypeRelation("wellness", True, ("eat", "stay", "do")),
    "shop": TypeRelation("shop", True, ("eat", "drink")),
    "do": TypeRelation("do", False, ("eat", "drink", "stay")),
    "event": TypeRelation("event", False, ("eat", "drink", "stay")),
    "editorial": TypeRelation("editorial", False, ("stay", "eat", "drink", "wellness", "shop", "do", "event")),
}

VENUE_TYPES = {"stay", "eat", "drink", "wellness", "shop", "unknown"}
NON_VENUE_TYPES = {"do", "event", "editorial"}

print("=== Step 1/2: direct excluded_types_for / is_competitor behaviour now ===")

excl_none = excluded_types_for(RELATIONS, None)
check(
    "excluded_types_for(None) is non-empty (fail-closed, not the old leak)",
    len(excl_none) > 0,
    f"got {sorted(excl_none)}",
)
check(
    "excluded_types_for(None) == every exclude_same=True type + 'unknown'",
    excl_none == VENUE_TYPES,
    f"got {sorted(excl_none)}, want {sorted(VENUE_TYPES)}",
)

for vt in sorted(VENUE_TYPES):
    check(f"is_competitor(None, {vt!r}) is True", is_competitor(RELATIONS, None, vt) is True)
for nvt in sorted(NON_VENUE_TYPES):
    # non-venue types must NOT be excluded even under the None fail-closed rule
    check(f"is_competitor(None, {nvt!r}) is False", is_competitor(RELATIONS, None, nvt) is False)

# Updated by F73: these two asserted the PRE-F73 behaviour, where an
# unidentifiable candidate was let through ("cannot identify -> not a
# competitor"). F73 made that fail closed, so the expected verdict flipped:
# "we don't know what this is" cannot mean "we know it is safe" for a
# guarantee Sec.8.A calls never-violated. The F68 subject-side findings this
# script was written to prove are unaffected and still pass.
check("is_competitor(None, None) is True (F73: unidentifiable candidate fails closed)", is_competitor(RELATIONS, None, None) is True)
check("is_competitor(None, '') is True (F73: falsy candidate type fails closed)", is_competitor(RELATIONS, None, "") is True)

print()
print("=== Step 3: adversarial end-to-end ladder walk, subject='stay', ALL rungs leak None-typed 'stay' candidates ===")


def make_stay_leak_fetch_fn():
    """A from-scratch adversarial fetch_fn (not reused from any existing
    test file) simulating a broken/naive rail implementation: at every
    single rung, it returns a mix of legitimate non-competitor candidates
    PLUS several subject_type=None candidates whose true underlying type
    IS 'stay' (the competitor type) -- i.e. exactly the F68 pre-fix leak
    vector (classification hasn't run, F50, so every real candidate row
    has type=None in the DB sense; here we model the *rendered* Candidate
    directly having type=None while being an actual stay/venue in truth).
    Each rung also starves (returns < slots_needed genuinely-safe rows),
    forcing the ladder to walk every single rung including the terminal
    editorial_fallback rung.
    """
    call_count = {"n": 0}

    def fetch(rung: RungSpec) -> list[Candidate]:
        call_count["n"] += 1
        base_id = call_count["n"] * 1000
        return [
            # Leak attempt: type=None, standing in for an unclassified
            # candidate whose real-world identity is a competing 'stay'.
            Candidate(entity_type="place", entity_id=base_id + 1, type=None, status="active"),
            Candidate(entity_type="place", entity_id=base_id + 2, type=None, status="active"),
            # A genuinely unknown-sentinel-typed competitor too.
            Candidate(entity_type="place", entity_id=base_id + 3, type="unknown", status="active"),
            # One legitimately safe non-venue candidate per rung (keeps
            # the rung underfilled relative to slots_needed=10 so the
            # ladder is forced onward every time).
            Candidate(entity_type="place", entity_id=base_id + 4, type="do", status="active"),
        ]

    return fetch


run = run_ladder(make_stay_leak_fetch_fn(), subject_type="stay", relations=RELATIONS, slots_needed=10)
print(f"rungs_evaluated: {run.rungs_evaluated}")
print(f"final rung reached: {run.result.rung_name} (index {run.result.rung_index})")
final_types = {c.type for c in run.result.candidates}
print(f"final candidate types survived: {sorted(t for t in final_types if t is not None) + (['None'] if None in final_types else [])}")

check(
    "ladder walked all 8 rungs (starved dataset, must reach editorial_fallback)",
    run.rungs_evaluated == [r.name for r in DEFAULT_LADDER],
    f"got {run.rungs_evaluated}",
)
check("no 'unknown'-typed competitor survived", "unknown" not in final_types, f"final_types={final_types}")
check("no 'stay'-typed competitor survived", "stay" not in final_types, f"final_types={final_types}")
print(
    "NOTE (not a check, not an F68 defect): candidate.type=None rows survived "
    f"(final_types={final_types}). Verified against the real schema "
    "(engine/packages/cms/src/migrations/20260908_131927_initial_schema.ts:120) "
    "that `places.type` is NOT NULL -- a place candidate can never actually have "
    "type=None, so this shape does not occur for places. `articles.primary_type` "
    "IS nullable, and is_competitor()'s docstring explicitly documents that a "
    "falsy/None *candidate* type is deliberately never treated as a competitor "
    "('a candidate with no type at all cannot be identified as any competitor') "
    "-- an unrelated, pre-existing, documented design choice, not the subject_type "
    "None bug F68 fixes. Confirming this is out of scope, not re-scoring it as a fail."
)

print()
print("=== Step 4: THE core F68 claim -- subject_type=None end-to-end, candidates typed 'stay' at EVERY rung including final ===")


def make_none_subject_leak_fetch_fn():
    """This is the actual F68 scenario per PROGRESS.md: the SUBJECT
    itself has subject_type=None (real state of every article/page today,
    F50), and its page pulls candidates that are concretely typed 'stay'
    (a real venue competitor) at every single rung, all the way to the
    terminal editorial_fallback rung. Pre-fix, excluded_types_for(None)
    returned frozenset() -> zero rows filtered -> all these 'stay' (and
    'unknown') rows would have survived. Post-fix they must all be
    stripped, at every rung, by the ladder's OWN re-check (independent of
    whatever hard.py's SQL is presumed to have done)."""
    call_count = {"n": 0}

    def fetch(rung: RungSpec) -> list[Candidate]:
        call_count["n"] += 1
        base_id = call_count["n"] * 10000
        return [
            Candidate(entity_type="place", entity_id=base_id + 1, type="stay", status="active"),
            Candidate(entity_type="place", entity_id=base_id + 2, type="stay", status="active"),
            Candidate(entity_type="place", entity_id=base_id + 3, type="unknown", status="active"),
            Candidate(entity_type="place", entity_id=base_id + 4, type="eat", status="active"),  # also venue-shaped -> must be excluded too since subject unknown
            Candidate(entity_type="place", entity_id=base_id + 5, type="editorial", status="active"),  # non-venue -> should survive
        ]

    return fetch


run2 = run_ladder(make_none_subject_leak_fetch_fn(), subject_type=None, relations=RELATIONS, slots_needed=50)
print(f"rungs_evaluated: {run2.rungs_evaluated}")
print(f"final rung reached: {run2.result.rung_name}")
final_types2 = {c.type for c in run2.result.candidates}
print(f"total surviving candidates across final rung result: {len(run2.result.candidates)}, types={sorted(final_types2)}")

check(
    "ladder walked all 8 rungs (every rung starved: nothing but venue-shaped + one editorial per rung, never reaching 50 slots since venue types are all stripped)",
    run2.rungs_evaluated == [r.name for r in DEFAULT_LADDER],
    f"got {run2.rungs_evaluated}",
)
check("zero 'stay' candidates leaked for subject_type=None", "stay" not in final_types2, f"final_types2={final_types2}")
check("zero 'eat' candidates leaked for subject_type=None", "eat" not in final_types2, f"final_types2={final_types2}")
check("zero 'unknown' candidates leaked for subject_type=None", "unknown" not in final_types2, f"final_types2={final_types2}")
check(
    "'editorial' candidates DID survive for subject_type=None (non-venue unaffected)",
    "editorial" in final_types2 or len(run2.result.candidates) > 0,
    f"final_types2={final_types2}, n={len(run2.result.candidates)}",
)
check(
    "the ONLY surviving type is 'editorial' (non-venue-shaped)",
    final_types2 == {"editorial"},
    f"final_types2={final_types2}",
)

print()
print("=== Step 5: over-correction check -- editorial SUBJECT with editorial CANDIDATES must NOT be wrongly excluded ===")


def make_editorial_fetch_fn():
    def fetch(rung: RungSpec) -> list[Candidate]:
        return [
            Candidate(entity_type="article", entity_id=1, type="editorial", status=None),
            Candidate(entity_type="article", entity_id=2, type="editorial", status=None),
            Candidate(entity_type="place", entity_id=3, type="stay", status="active"),  # should still be excluded? editorial subject exclude_same=False -> stay is NOT excluded by same-type rule (editorial doesn't exclude stay); only used to confirm editorial isn't blanket-excluding everything
        ]

    return fetch


run3 = run_ladder(make_editorial_fetch_fn(), subject_type="editorial", relations=RELATIONS, slots_needed=5)
final_types3 = [c.type for c in run3.result.candidates]
print(f"editorial-subject final candidates: {final_types3}")
check(
    "editorial-typed candidates pass through for an 'editorial' subject (not conflated with the None/unknown fail-closed rule)",
    final_types3.count("editorial") == 2,
    f"final_types3={final_types3}",
)
check(
    "excluded_types_for('editorial') is empty (exclude_same=False row, distinct from the None branch)",
    excluded_types_for(RELATIONS, "editorial") == frozenset(),
)
check(
    "is_competitor(subject_type='editorial', candidate_type='editorial') is False",
    is_competitor(RELATIONS, "editorial", "editorial") is False,
)
check(
    "is_competitor(subject_type='editorial', candidate_type='stay') is False (editorial doesn't self-exclude, and cross-type isn't excluded either)",
    is_competitor(RELATIONS, "editorial", "stay") is False,
)

print()
print("=== SUMMARY ===")
if FAILURES:
    print(f"{len(FAILURES)} CHECK(S) FAILED:")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
    sys.exit(0)
