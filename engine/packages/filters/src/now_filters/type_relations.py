"""Reads `engine.type_relations` (ARCHITECTURE.md Sec.4/Sec.8.A) -- the
commercial competitor-exclusion matrix. Real table, real seed data (8 L1
types, per-site overridable in place); nothing here is synthetic.

This module is the ONLY place `exclude_same`/`complements`/`competes_with`
are interpreted, so the competitor-exclusion promise (Sec.1 principle 6:
"It never relaxes, at any fallback rung, for any tier") has exactly one
implementation to audit.

`competes_with` (migration 0008, 2026-09-24) is the second exclusion axis:
`exclude_same` says "excludes its own L1 type"; `competes_with` says
"also excludes THESE OTHER L1 types" -- the owner's "F&B is one class"
rule (`eat`/`drink`) needs the second axis because they are not each
other's "own kind", they are two different types the business treats as
one competitive class.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

_SELECT_ALL = text("SELECT type, exclude_same, complements, competes_with FROM engine.type_relations")


@dataclass(frozen=True)
class TypeRelation:
    type: str
    exclude_same: bool
    complements: tuple[str, ...]
    # Edition 2 (2026-09-24, migration 0008): a SECOND, narrower exclusion
    # axis alongside `exclude_same`. The owner's rule ("never restaurant,
    # cafe or F&B" on a restaurant story) named `eat`/`drink` as ONE
    # competitive class even though they are two separate L1 types --
    # `exclude_same` cannot express "excludes a DIFFERENT type", only "excludes
    # its own kind". `competes_with` is a per-row list of other L1 types this
    # type must never co-recommend, regardless of `complements`. See
    # `excluded_types_for`'s docstring for how the two axes combine.
    competes_with: tuple[str, ...] = ()


def load_type_relations(conn: Connection) -> dict[str, TypeRelation]:
    rows = conn.execute(_SELECT_ALL).fetchall()
    return {
        r.type: TypeRelation(
            type=r.type,
            exclude_same=bool(r.exclude_same),
            complements=tuple(r.complements or ()),
            competes_with=tuple(r.competes_with or ()),
        )
        for r in rows
    }


def excluded_types_for(relations: dict[str, TypeRelation], subject_type: str | None) -> frozenset[str]:
    """The set of L1 types that must NEVER appear alongside `subject_type`
    on its own page, per Sec.8.A's competitor rule.

    - `exclude_same=True` -> subject_type itself joins the excluded set
      (a villa is still a competitor to a hotel, ARCHITECTURE.md Sec.4).
    - `complements` is a co-recommendation whitelist, not a competitor
      list -- explicitly NOT unioned into the excluded set (this was the
      exact mechanism QA.2 verified per PROGRESS.md F27).

    F57 (PROGRESS.md): the `unknown` L1 type (F49) is the fail-closed
    sentinel for the 177 still-unclassified places -- by definition, an
    `unknown`-typed candidate MIGHT be any venue type, including the
    subject's own. F49 proved the self-exclusion direction (an `unknown`
    subject excludes other `unknown` candidates, via `exclude_same=True`
    on its own row) but left the cross-type direction open: a `stay`
    subject's row only names `stay` in its own excluded set, so an
    `unknown`-typed hotel could still surface as a "competitor" suggestion
    on a genuine hotel's page.

    Fix, expressed as a DATA-DRIVEN rule rather than a hardcoded type
    name check: every subject type for which `exclude_same=True` is
    already the platform's signal that this type is "commercially
    competitor-sensitive" (ARCHITECTURE.md Sec.4 -- exactly the 5 real
    venue L1 types: stay/eat/drink/wellness/shop, plus `unknown` itself).
    Any such subject must ALSO treat `unknown` as a competitor, because an
    unclassified place is possibly-that-subject's-own-type and cannot be
    ruled out. Editorial-shaped subjects (`editorial`, `do`, `event` --
    the three `exclude_same=False` rows) are unaffected: they are not
    commercial venues, they already list every venue type as a
    complement, and Sec.4's matrix already exempts them from the
    same-type rule for the same reason.

    Migration 0008 (2026-09-24) added a second axis, `competes_with`: two
    DIFFERENT L1 types the owner named as one competitive class ("never
    restaurant, cafe or F&B" -- `eat`/`drink`). `exclude_same` only ever
    adds the subject's OWN type to the excluded set; it has nothing to say
    about a different type that nonetheless must never co-recommend. Every
    subject's `competes_with` list is unioned in below, unconditionally --
    unlike `exclude_same`, this axis is not itself gated on "is this a
    venue-shaped type", because the DATA is the gate: an `exclude_same=False`
    row's `competes_with` is `{}` by construction (nothing today populates
    it for editorial/do/event), so the union is a no-op for them, not a
    special case this function has to know about.

    `unknown` the literal type name is still a special case in the one
    place that names it (this line) -- deliberately: it is not "one more
    catalog type" a data row can express generically, it is THE sentinel
    for "we don't know, so assume the worst", which is a property of the
    taxonomy design, not of any one site's `type_relations` data. Keying
    the *applicability* of the rule off `exclude_same` (data) rather than
    off a hardcoded list of venue type names keeps this correct if the
    venue type vocabulary ever changes, while keeping `unknown` itself as
    an explicit, auditable constant rather than a magic row property.

    F68 (PROGRESS.md): a `None` (unclassified) subject_type used to return
    an EMPTY excluded set here -- "no relation row to consult" was treated
    as "nothing to exclude". That is backwards for a commercial guarantee
    (Sec.8.A: "never violated" -- not a ranking preference) and is the
    real state of every article in the archive today (F50: `primary_type`
    is NULL archive-wide until E2.1 runs). An unclassified subject could be
    ANY type, including any venue type, so it cannot rule out ANY
    venue-shaped competitor -- the only fail-closed answer is to exclude
    the union of every `exclude_same=True` type (the venue-shaped L1 types,
    data-driven exactly as above) plus `unknown` itself. This is strictly
    the most restrictive case, by construction it is a superset of every
    known venue subject's own excluded set, so it never under-excludes
    relative to any concrete type. A KNOWN subject_type -- including the
    editorial-shaped ones (`editorial`/`do`/`event`) -- is unaffected by
    this branch entirely; "we don't know the type" is not the same
    condition as "we know it's editorial", and must not be conflated with
    it.
    """
    if subject_type is None:
        base = {r.type for r in relations.values() if r.exclude_same}
        # Fail-closed must stay a superset of every KNOWN venue subject's own
        # excluded set (this function's own invariant, stated above) -- so
        # the None branch also unions every exclude_same=True row's
        # competes_with, not just its own type name. In practice this is
        # already covered when competes_with pairs are symmetric within the
        # exclude_same=True set (eat/drink both have exclude_same=True, so
        # each is already in `base`), but computing it explicitly rather
        # than relying on that symmetry keeps the invariant true even if a
        # future `competes_with` entry points outside that set.
        competes = {t for r in relations.values() if r.exclude_same for t in r.competes_with}
        return frozenset(base | competes | {"unknown"})
    if not subject_type:
        return frozenset()
    relation = relations.get(subject_type)
    if relation is None:
        return frozenset()
    if not relation.exclude_same:
        return frozenset()
    return frozenset({subject_type, "unknown"} | set(relation.competes_with))


def is_competitor(relations: dict[str, TypeRelation], subject_type: str | None, candidate_type: str | None) -> bool:
    """True if `candidate_type` must be excluded from a rail built for
    `subject_type`. Symmetric by construction (both look up the same
    `exclude_same` flag keyed off `subject_type` only -- ARCHITECTURE.md
    Sec.4's matrix is defined per row-type, not pairwise), matching the
    single-direction exclusion rule as specified: "same L1 type excluded".

    F68: `subject_type is None` used to short-circuit to `False` here
    unconditionally -- a second, independent copy of the exact bug fixed
    in `excluded_types_for`. Fixed by routing through `excluded_types_for`
    for every subject, known or not (below).

    F73/F74 (PROGRESS.md): `candidate_type` being falsy used to be a
    SEPARATE early-return straight to `False` -- "a candidate with no type
    at all cannot be identified as any competitor". Defensible read in
    isolation, but it directly contradicted `hard.py`'s SQL, where
    `primary_type::text != ALL(:excluded_types)` evaluates to SQL NULL for
    a NULL `primary_type` and a NULL WHERE-clause result drops the row --
    i.e. the SQL path already failed CLOSED (excludes) on exactly the
    input this function failed OPEN (includes) on. Two paths silently
    disagreeing on the one commercial guarantee Sec.8.A calls "never
    violated" is the actual defect (F73), independent of which answer is
    right.

    The resolution applies the SAME fail-closed principle F68 already
    established for an unknown SUBJECT to an unknown CANDIDATE: "we don't
    know its type" cannot be treated as "we know it's safe" for a
    guarantee this important. An unclassified candidate might be any
    type, including the subject's own -- exactly the reasoning
    `excluded_types_for` already applies to `subject_type is None` -- so
    it is now treated as excluded whenever the subject excludes ANYTHING
    (`excluded_types_for(...)` non-empty). When the subject is a KNOWN
    non-venue type (`editorial`/`do`/`event`, `exclude_same=False` --
    `excluded_types_for` returns an empty set), there is nothing to guard
    against regardless of the candidate's type, so a falsy candidate_type
    still correctly resolves to `False` there -- this branch does not
    turn "no exclusion applies" into "everything is a competitor".

    **`places` vs `articles` asymmetry, addressed, not ignored**:
    `places.type` is `NOT NULL` (schema-enforced) and F49/F57 already gave
    unclassified places an explicit, real sentinel value (`type='unknown'`,
    `exclude_same=True`) that participates in ordinary string comparison
    -- a place candidate is NEVER falsy here, in production or in tests,
    so this branch is dead code for `places` by construction, not merely
    by convention. `articles.primary_type` has no such sentinel: NULL
    genuinely means "not yet classified" (F50 -- 4,772/4,772 today), so
    this branch is the ONLY place the ambiguity is live. That asymmetry is
    exactly why a single shared rule -- fail closed on an unidentifiable
    candidate wherever exclusion is active at all -- is the right level to
    fix this at, rather than special-casing `articles`: it produces the
    already-existing, correct, no-op behaviour for `places` for free.

    Consequence, stated plainly: while `primary_type` is NULL
    archive-wide, this makes every real article a candidate-side
    competitor risk for every rail whose subject excludes anything (which
    per F68 is every rail today, since every real subject_type is also
    None) -- the rails return nothing on real content until E2.1
    classifies the archive. That is F50/F74's conclusion, not a new one;
    this fix does not change whether real content flows today, only makes
    the two code paths agree on why it doesn't."""
    excluded = excluded_types_for(relations, subject_type)
    if not excluded:
        return False
    if not candidate_type:
        return True
    return candidate_type in excluded
