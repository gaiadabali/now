"""`classification.reviewed` -> `engine.entity_terms`: the last link of E2.8.

An editor's decision already reaches `public.classification_reviews` and the
article's own `primaryType`/`format` field. It stopped there. `engine
.entity_terms` -- what ranking, faceting and §8.A competitor exclusion
actually read -- kept the classifier's guess, at the classifier's
confidence, with `source` still `ai`. Measured while this was written: in
one city, 3,630 `type` and 3,109 `format` assignments, every single one
below the 0.85 gate `now_blender.decay.is_format_trusted` applies. A
reviewer working through that queue was writing into a store nothing reads.

**Why the worker holds the pen.** ARCHITECTURE.md §1 rule 2 -- Payload owns
`public`, Alembic owns `engine`. The CMS *cannot* write this row; that
boundary is the entire reason the event exists.
`engine/packages/cms/scripts/verify-review-no-clobber.mjs` has been standing
in for this module with raw SQL, clearly labelled as a simulation. The SQL
below is deliberately the same shape, so that script stays a valid proof of
the no-clobber guarantee it tests rather than becoming a description of
something that no longer happens.

## Confirm, correct, reject -- and why `previous_term_id` alone is a trap

`review_state` separates the three outcomes, but the *cleanup* they need is
decided by something the event does not carry: whether the facet holds one
value or many. `now_platform.engine.facets.cardinality` already answers
that -- `type`/`format`/`subtype`/`price_band` are `single`, `location` and
the six tagging facets are `multi` -- so this module reads it rather than
naming a facet (the same reason §3.5 bans naming a city).

  - **single**: the decision is *the* value for that facet. Every other row
    for this entity within the facet is superseded, whatever put it there.
  - **multi**: co-assigned terms are legitimate -- an article can be in two
    neighbourhoods -- so only the term the event names as superseded goes.

Trusting `previous_term_id` for the single case looked sufficient and is
not. `previous_term_id` is `doc.termId`, the AI's *original* proposal,
frozen on the review row; `ClassificationReviews.ts` calls that row a
snapshot and means it. Decide the same review twice -- corrected to
`drink`, then corrected again to `eat` -- and the second event still
reports the first AI guess as `previous_term_id`, so a `previous_term_id`
delete would leave `drink` behind and the article would carry two types.
Superseding the whole facet is immune to that, and to redelivery, because
it is defined by the *destination* state rather than by a diff.

For `multi` facets that immunity is not available from this payload: there
is no field saying which of several co-assigned terms the reviewer meant to
drop beyond `previous_term_id`, and inventing one is a CMS change this task
explicitly forbids. Logged as `supersede=previous_only` so the gap is
visible in the log rather than only in this comment.

## What is deliberately NOT guarded

The classifier's upsert carries `WHERE entity_terms.source <> 'editor'`
(`now_classifier.db`) so a re-run can never overwrite a human. This module
has no such predicate, on purpose: that guard protects a human decision
from a *machine*, and applying it here would make a human's *second*
decision a silent no-op -- the exact failure it exists to prevent, pointed
the wrong way.

Nothing here writes `public.articles`. The CMS hook already did, through
Payload's own Local API, before it published. A second writer for a
Payload-owned column would be the F132 two-stores-disagree bug rebuilt on
purpose.

## Idempotency

Redelivery is a property of the stream, not an exception. Both statements
are defined by the end state, not by a transition: the DELETE is a no-op
once the superseded row is gone, and the INSERT ... ON CONFLICT DO UPDATE
rewrites the same three values. They run in one transaction so a crash
between them cannot leave an entity with no row for a facet it has a
decision for.

What this canNOT do is reject a *stale* event -- an old decision redelivered
from the pending list after a newer one was applied would win, because
`engine.entity_terms` has no column recording when its row was decided
(`created_at` is insert time, and an upsert does not move it). Fixing that
means `reviewed_at` on the table, which is DDL, which is senior-db's seat
and an architect-approved migration. Reported, not improvised.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import Engine, text

logger = logging.getLogger("app.classification")

EVENT = "classification.reviewed"

#: `engine.facets.cardinality`'s two values. Named rather than inlined so the
#: single/multi branch below reads as the vocabulary's own distinction and
#: not as a local convention.
SINGLE = "single"

#: `weight` on an editor row. 1.0 matches what `verify-review-no-clobber.mjs`
#: writes for the same decision and what the classifier writes for a term it
#: is sure of; a human decision is not a partial assignment.
EDITOR_WEIGHT = 1.0

#: Used when the event reports no confidence but does carry a term -- the
#: `unclassifiable` case for `type`, which resolves to the seeded `unknown`
#: sentinel (F49) rather than to nothing. `source='editor'` is already
#: unconditionally trusted by `now_blender.decay`, but `now_search.facets`
#: and anything else gating on the number alone would read NULL as
#: "unverifiable provenance" and fail closed -- which would silently discard
#: a decision a human was certain about. The certainty is real: the human is
#: sure the article is unclassifiable, and for `type` that certainty has a
#: real term to point at.
EDITOR_CONFIDENCE = 1.0


_FACET_SHAPE_SQL = text(
    """
    select f.cardinality,
           coalesce(array_agg(t.id::text) filter (where t.id is not null), '{}') as term_ids
    from engine.facets f
    left join engine.terms t on t.facet_id = f.id
    where f.key = :facet_key
    group by f.cardinality
    """
)

# Supersede within a single-valued facet: everything for this entity that
# belongs to the facet except the term just decided. `keep_term_id` is always
# present here -- the no-term case takes the statement below -- so this needs
# no NULL branch, which keeps the parameter typed as a uuid for psycopg.
_DELETE_OTHER_FACET_TERMS_SQL = text(
    """
    delete from engine.entity_terms
    where entity_type = :entity_type
      and entity_id = :entity_id
      and term_id = any(cast(:facet_term_ids as uuid[]))
      and term_id <> cast(:keep_term_id as uuid)
    """
)

# The retraction: a decision with no term at all (`unclassifiable` on a facet
# with no sentinel, e.g. `format`). The honest end state is no row, not the
# classifier's debunked guess left standing -- the same judgment
# `_DELETE_ALL_FACET_TERMS_SQL` makes in `now_classifier.db` when a re-run
# abstains.
_DELETE_ALL_FACET_TERMS_SQL = text(
    """
    delete from engine.entity_terms
    where entity_type = :entity_type
      and entity_id = :entity_id
      and term_id = any(cast(:facet_term_ids as uuid[]))
    """
)

# Multi-valued facets: only the term the event names. See the module
# docstring for why this is weaker and cannot be strengthened from here.
_DELETE_PREVIOUS_TERM_SQL = text(
    """
    delete from engine.entity_terms
    where entity_type = :entity_type
      and entity_id = :entity_id
      and term_id = cast(:previous_term_id as uuid)
    """
)

_UPSERT_EDITOR_TERM_SQL = text(
    """
    insert into engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence)
    values (:entity_type, :entity_id, cast(:term_id as uuid), :weight, 'editor', :confidence)
    on conflict (entity_type, entity_id, term_id)
    do update set weight = excluded.weight,
                  source = excluded.source,
                  confidence = excluded.confidence
    """
)


@dataclass(frozen=True)
class FacetShape:
    """What the platform vocabulary says about one facet. `term_ids` is every
    term in it, because a cross-database FK is impossible (§2) and the facet
    membership test therefore has to travel to the city as a literal array --
    the same application-side resolution `now_classifier.vocabulary` does."""

    cardinality: str
    term_ids: list[str]

    @property
    def single_valued(self) -> bool:
        return self.cardinality == SINGLE


@dataclass(frozen=True)
class Decision:
    """The event, reduced to what the write needs. Built by `decision_from`
    so that every "is this event usable" question is answered once, before a
    database connection is opened."""

    site_slug: str
    entity_type: str
    entity_id: str
    facet_key: str
    review_id: object
    term_id: str | None
    previous_term_id: str | None
    value: str | None
    review_state: str | None
    confidence: float | None


class UnusableEvent(Exception):
    """The event cannot be applied and never will be. Raised rather than
    returned so a caller cannot forget to check: every raise site is a reason
    to ACK and move on, never a reason to retry."""


def decision_from(event: dict) -> Decision:
    payload = event.get("payload") or {}

    entity_id = event.get("entity_id")
    if entity_id is None or str(entity_id).strip() == "":
        raise UnusableEvent("no entity_id")
    entity_type = event.get("entity_type")
    if not entity_type:
        raise UnusableEvent("no entity_type")
    facet_key = payload.get("facet_key")
    if not facet_key:
        raise UnusableEvent("no facet_key")

    term_id = payload.get("term_id")
    value = payload.get("value")
    if term_id is None and value is not None:
        # The reviewer decided something real and the CMS could not map it to
        # a platform term. Untagging the article on the back of that would
        # turn a vocabulary gap into data loss, and writing nothing at all
        # leaves the classifier's guess standing -- both are wrong, so this
        # refuses and says so loudly. Same "refuse and flag, never guess"
        # stance `now_classifier.db` takes for the drift it cannot resolve.
        raise UnusableEvent(f"value={value!r} carries no term_id (vocabulary gap on the CMS side)")

    raw_confidence = payload.get("confidence")
    return Decision(
        site_slug=str(event.get("site_slug") or ""),
        entity_type=str(entity_type),
        entity_id=str(entity_id),
        facet_key=str(facet_key),
        review_id=payload.get("review_id"),
        term_id=str(term_id) if term_id is not None else None,
        previous_term_id=(
            str(payload["previous_term_id"]) if payload.get("previous_term_id") is not None else None
        ),
        value=value,
        review_state=payload.get("review_state"),
        confidence=float(raw_confidence) if isinstance(raw_confidence, (int, float)) else None,
    )


def load_facet_shape(platform: Engine, facet_key: str) -> FacetShape | None:
    with platform.connect() as conn:
        row = conn.execute(_FACET_SHAPE_SQL, {"facet_key": facet_key}).first()
    if row is None:
        return None
    return FacetShape(cardinality=row[0], term_ids=list(row[1] or []))


def apply_decision(city: Engine, shape: FacetShape, decision: Decision) -> str:
    """Write one decision into `engine.entity_terms`. Returns a short status
    for the log and the caller's counters.

    One transaction, supersede-then-write. The order matters only for the
    `single` facet case, where the DELETE is scoped to "everything in the
    facet except the term being kept" -- doing it first means the row count
    it reports is the number genuinely retired, which is what the log line
    needs to answer "did the old tag go away?"."""

    params = {"entity_type": decision.entity_type, "entity_id": decision.entity_id}
    superseded = 0

    with city.begin() as conn:
        if shape.single_valued:
            supersede_mode = "facet"
            if decision.term_id is None:
                superseded = conn.execute(
                    _DELETE_ALL_FACET_TERMS_SQL, {**params, "facet_term_ids": shape.term_ids}
                ).rowcount
            else:
                superseded = conn.execute(
                    _DELETE_OTHER_FACET_TERMS_SQL,
                    {**params, "facet_term_ids": shape.term_ids, "keep_term_id": decision.term_id},
                ).rowcount
        else:
            supersede_mode = "previous_only"
            if decision.previous_term_id and decision.previous_term_id != decision.term_id:
                superseded = conn.execute(
                    _DELETE_PREVIOUS_TERM_SQL,
                    {**params, "previous_term_id": decision.previous_term_id},
                ).rowcount

        if decision.term_id is not None:
            conn.execute(
                _UPSERT_EDITOR_TERM_SQL,
                {
                    **params,
                    "term_id": decision.term_id,
                    "weight": EDITOR_WEIGHT,
                    "confidence": (
                        decision.confidence if decision.confidence is not None else EDITOR_CONFIDENCE
                    ),
                },
            )

    status = "retracted" if decision.term_id is None else "applied"
    # One line, every field an operator needs to answer "did this decision
    # land?" without opening a debugger or correlating two logs: which review,
    # which city, which row, what moved, and how much was retired.
    logger.info(
        "%s review=%s site=%s %s:%s facet=%s state=%s %s -> %s "
        "(source=editor, superseded=%d via %s) [%s]",
        EVENT,
        decision.review_id,
        decision.site_slug,
        decision.entity_type,
        decision.entity_id,
        decision.facet_key,
        decision.review_state,
        decision.previous_term_id or "-",
        decision.term_id or "(none)",
        superseded,
        supersede_mode,
        status,
    )
    return status
