"""City-DB reads and writes. Idempotent by construction:

- `public.articles.primary_type` / `.format`: kept in sync with
  `engine.entity_terms` -- see F132 below for why "only ever set from
  NULL" (this module's ORIGINAL rule) was itself the bug.
- `engine.entity_terms`: `INSERT ... ON CONFLICT (entity_type, entity_id,
  term_id) DO UPDATE ... WHERE entity_terms.source <> 'editor'` -- re-running
  updates the classifier's own prior write, but an editor-sourced row (once
  `engine-worker` or a CMS action writes one) is never overwritten by a
  re-run (F86's guard, enforced here on the write side since the DB-level
  trigger F86 asks for does not exist yet).
- `classification_reviews`: only a row still `review_state = 'pending'` is
  ever updated in place on a re-run; anything an editor has already acted on
  (`accepted` / `corrected` / `unclassifiable`) is left alone.

## F132 -- the two-stores-disagree bug, root cause and fix

`write_results` writes the SAME classification decision to two places:
`public.articles.primary_type`/`.format` (one column each, read by
`now_rails.subject` -- drives competitor exclusion) and
`engine.entity_terms` (one term-row per facet, read by facet queries, the
F133 decay gate, and F131's LLM apply-step). Before this fix the two
writes had DIFFERENT re-run semantics:

  - `entity_terms` was upserted (overwrite-on-reclassify) -- and, since
    F125's stale-retraction fix (see `_DELETE_STALE_FACET_TERMS_SQL` /
    `_DELETE_ALL_FACET_TERMS_SQL` below), it is RETRACTED (row deleted)
    the moment a later run proposes a different value or downgrades the
    facet to review. It always reflects the LATEST run's decision.
  - `articles.primary_type`/`.format` was written with
    `coalesce(primary_type, :new_value)` -- "set once, never touch again
    once non-NULL". That guard exists because `public.articles` has NO
    provenance column (verified -- F131/F132): a human CMS edit is
    indistinguishable from a machine write, so the ORIGINAL author of this
    module chose to never overwrite a non-NULL value, at all, ever.

The result: an article classified by an EARLY run (e.g. E2.1's original
pass, 2026-09-08) got its `articles` value frozen forever, while EVERY
subsequent re-run (F125's routing fixes, 2026-09-11) kept moving
`entity_terms` to the new, better answer. Verified live on the exact
samples F132 reported (wp11/31/51, `now_jakarta`): `articles.updated_at`
sits at 2026-09-08 16:05:57 (the E2.1 run) while the disagreeing
`entity_terms` row carries `created_at` 2026-09-11 (F125's re-run) -- two
DIFFERENT runs of this same tool, not a CMS edit and not a cardinality
bug. The "924 missing type row" shape is the same mechanism's other face:
when a later run downgrades a facet to review, `entity_terms`'s row is
retracted (correctly -- "we no longer confidently know this") but
`articles` had no retraction path at all, so it kept the stale value.

**The fix, without a schema migration** (a `primary_type_source` enum on
`public.articles` is the clean fix and is proposed, not implemented here
-- see PROGRESS.md F131/F132 -- it is a Payload-owned migration, senior-db/
architect owned): treat `entity_terms`'s CURRENT (pre-this-write) value as
a proxy for "what the classifier itself last put in `articles`". Before
touching either store for `type`/`format`, `_facet_sync_status` checks
whether `articles`'s current value still matches what `entity_terms`
currently holds for that facet (and that the current `entity_terms` row,
if any, is not `editor`-sourced). Only when that holds -- i.e. `articles`
is still demonstrably machine-owned, unedited since the last write -- does
this run evolve BOTH stores together, atomically, in the one transaction
already open per city (`write_results`'s `engine.begin()`). When it does
not hold (a genuine editor edit, or a row this exact bug already drifted),
`articles` is left untouched and the drift is counted
(`WriteStats.articles_facet_drift_skipped`) rather than silently
guessed at -- the same "refuse and flag, never guess" judgment call
F131's LLM-apply writer already made for the identical schema gap.
"""
from __future__ import annotations

from dataclasses import dataclass

from now_db.settings import city_database_url
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .confidence import AUTO_APPLY_AT_OR_ABOVE, band
from .resolve import ClassificationResult
from .vocabulary import TermIndex, term_uuid


def make_engine(db_ref: str) -> Engine:
    return create_engine(city_database_url(db_ref))


def fetch_id_by_wp_id(engine: Engine) -> dict[int, int]:
    with engine.connect() as conn:
        rows = conn.execute(text("select id, legacy_wp_id from public.articles where legacy_wp_id is not null")).fetchall()
    return {int(r[1]): r[0] for r in rows}


_SELECT_ARTICLE_FACETS_SQL = text(
    """
    select primary_type::text, format::text from public.articles where id = :article_id
    """
)

# F132: unconditional SET (not `coalesce`) -- callers only reach this once
# `_facet_sync_status` has already established it is safe to move BOTH
# stores together this run. Pass through the prior value for any facet
# this run isn't touching (see `write_results`) rather than relying on
# `coalesce`, which is what let the two stores drift apart in the first
# place: `coalesce` cannot express "retract to NULL", only "leave alone
# if already set".
_SET_ARTICLE_TYPE_FORMAT_SQL = text(
    """
    update public.articles
    set primary_type = cast(:primary_type as enum_articles_primary_type),
        format = cast(:format as enum_articles_format)
    where id = :article_id
    """
)

# F132: at most one non-retracted row is expected per (entity, facet) --
# `_DELETE_STALE_FACET_TERMS_SQL`/`_DELETE_ALL_FACET_TERMS_SQL` (F125) keep
# it that way. Read BEFORE this run's own writes touch the facet, so it
# reflects what `articles` was checked against the LAST time either store
# was written.
_SELECT_FACET_ENTITY_TERM_SQL = text(
    """
    select term_id::text, source
    from engine.entity_terms
    where entity_type = 'article' and entity_id = :entity_id
      and term_id = any(cast(:facet_term_ids as uuid[]))
    """
)

_UPSERT_ENTITY_TERM_SQL = text(
    """
    insert into engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence)
    values ('article', :entity_id, cast(:term_id as uuid), 1.0, :source, :confidence)
    on conflict (entity_type, entity_id, term_id)
    do update set weight = excluded.weight, source = excluded.source, confidence = excluded.confidence
    where engine.entity_terms.source <> 'editor'
    """
)

# F120 re-run finding (not new to this ticket, but surfaced by it): the
# upsert above only ever handles a re-run proposing the SAME term again --
# it has no way to retract a PREVIOUS run's accepted term for a
# single-valued facet (type/subtype/format) when this run's fresh proposal
# is a DIFFERENT term for that facet (e.g. routing flips a `cue_confident`
# article's type from the keyword-cue's old value to the embeddings
# centroid's different prediction, which is the entire point of F120's
# routing). Left alone, the OLD term row simply never gets touched and
# sits beside the new one forever -- exactly the same shape of bug F108
# reported for a title-match false positive (a stale wrong location row no
# later run ever removes), just for type/format/subtype instead of
# location. Scoped tightly: only deletes OTHER rows for the same
# (entity, facet), and never an `editor`-sourced row.
_DELETE_STALE_FACET_TERMS_SQL = text(
    """
    delete from engine.entity_terms
    where entity_type = 'article' and entity_id = :entity_id
      and term_id = any(cast(:other_term_ids as uuid[]))
      and term_id <> cast(:keep_term_id as uuid)
      and source <> 'editor'
    """
)

# Same retraction, for the case where THIS run has NO new value to write at
# all (the facet downgrades to review this time -- e.g. an F120-routed
# embeddings_centroid band abstains for this one article). Verified live,
# not theoretical: wp_id 70 carried a stale `type` row at the old invented
# CUE_CONFIDENT=0.93 from a run before this ticket's routing existed, while
# THIS run's cue instrument itself abstains for it (no cue cleared its
# margin threshold) and correctly proposes only a low-confidence review
# item -- with no "keep" id to spare, every non-editor row for the facet is
# removed: an honest "we no longer know" (send to review) must not leave a
# debunked, invented-number fact sitting in `engine.entity_terms` as if it
# were still endorsed.
_DELETE_ALL_FACET_TERMS_SQL = text(
    """
    delete from engine.entity_terms
    where entity_type = 'article' and entity_id = :entity_id
      and term_id = any(cast(:term_ids as uuid[]))
      and source <> 'editor'
    """
)

# One pending proposal per facet per article is the intended shape for
# type/subtype/format; `location` is multi-valued so it can legitimately
# carry several distinct proposed_value rows for the same facet_key, hence
# the extra proposed_value match for that one facet.
_FIND_PENDING_SQL = text(
    """
    select cr.id
    from classification_reviews cr
    join classification_reviews_rels rel on rel.parent_id = cr.id and rel.path = 'entity'
    where rel.articles_id = :article_id
      and cr.facet_key = cast(:facet_key as enum_classification_reviews_facet_key)
      and cr.review_state = 'pending'
      and (:facet_key <> 'location' or cr.proposed_value = :proposed_value)
    """
)

_UPDATE_REVIEW_SQL = text(
    """
    update classification_reviews
    set legacy_category = :legacy_category,
        proposed_value = :proposed_value,
        confidence = :confidence,
        confidence_band = cast(:confidence_band as enum_classification_reviews_confidence_band),
        reasoning = :reasoning,
        source = cast(:source as enum_classification_reviews_source),
        updated_at = now()
    where id = :id
    """
)

_INSERT_REVIEW_SQL = text(
    """
    insert into classification_reviews
        (entity_type, legacy_category, facet_key, term_id, proposed_value, confidence,
         confidence_band, reasoning, source, weight, review_state, site_slug)
    values
        ('article', :legacy_category, cast(:facet_key as enum_classification_reviews_facet_key), :term_id,
         :proposed_value, :confidence, cast(:confidence_band as enum_classification_reviews_confidence_band),
         :reasoning, cast(:source as enum_classification_reviews_source), 1.0, 'pending', :site_slug)
    returning id
    """
)

_INSERT_REVIEW_REL_SQL = text(
    """
    insert into classification_reviews_rels (parent_id, path, articles_id, "order")
    values (:parent_id, 'entity', :article_id, 0)
    """
)


@dataclass
class WriteStats:
    type_accepted: int = 0
    type_reviewed: int = 0
    format_accepted: int = 0
    format_reviewed: int = 0
    subtype_accepted: int = 0
    subtype_reviewed: int = 0
    location_accepted: int = 0
    location_reviewed: int = 0
    vocabulary_misses: int = 0
    stale_facet_terms_removed: int = 0  # see _DELETE_STALE_FACET_TERMS_SQL
    # F132: (article, facet) pairs where `articles.primary_type`/`.format`
    # was evolved together with `entity_terms` THIS run (new accepted value,
    # or retracted to NULL alongside entity_terms's own retraction).
    articles_facets_synced: int = 0
    # F132: (article, facet) pairs where `articles` was left untouched
    # because it no longer demonstrably matched `entity_terms`'s prior
    # value (a genuine editor edit, or a row this bug already drifted) --
    # never guessed at, always counted so it's visible, not silent.
    articles_facet_drift_skipped: int = 0


def _all_term_ids_for_facet(terms: TermIndex, facet_key: str) -> list[str]:
    return [uuid_ for uuid_, _parent in terms.by_facet.get(facet_key, {}).values()]


def _facet_sync_status(
    conn, entity_id: str, prior_value: str | None, terms: TermIndex, facet_key: str
) -> tuple[bool, str | None]:
    """F132. Is it safe to evolve `articles.<facet>` together with
    `entity_terms` THIS run? True unless `articles` currently holds a
    value that `entity_terms` (read BEFORE this run's own writes touch the
    facet) does not corroborate -- which means either a genuine editor/CMS
    edit, or a row this exact bug already drifted. Returns
    `(in_sync, reason_if_not)`; `reason` is machine-readable, matching the
    `skip_reasons` convention `now_eval.calibration.apply_llm_labels`
    already established for the identical judgment call.
    """
    if prior_value is None:
        return True, None  # nothing to protect -- free to write
    all_ids = _all_term_ids_for_facet(terms, facet_key)
    if not all_ids:
        return False, "no_vocabulary"
    row = conn.execute(
        _SELECT_FACET_ENTITY_TERM_SQL, {"entity_id": entity_id, "facet_term_ids": all_ids}
    ).fetchone()
    if row is None:
        return False, "no_entity_terms_row"
    term_id, source = row
    if source == "editor":
        return False, "editor_owned"
    prior_uuid = term_uuid(terms, facet_key, prior_value)
    if prior_uuid is None or prior_uuid.lower() != str(term_id).lower():
        return False, "articles_entity_terms_drift"
    return True, None


def write_results(
    engine: Engine,
    id_by_wp_id: dict[int, int],
    results: list[ClassificationResult],
    terms: TermIndex,
    site_slug: str,
    dry_run: bool = False,
) -> WriteStats:
    stats = WriteStats()
    with engine.begin() as conn:
        for r in results:
            article_id = id_by_wp_id.get(r.wp_id)
            if article_id is None:
                continue
            entity_id = str(article_id)

            # F132: read `articles`'s CURRENT type/format and check each
            # against `entity_terms`'s CURRENT (pre-this-write) value
            # BEFORE any write below touches either -- this is what lets
            # both stores move together atomically further down, and what
            # lets a genuine drift (editor edit, or a row this bug already
            # produced) be detected instead of blindly overwritten.
            prior_type = prior_format = None
            facet_sync: dict[str, tuple[bool, str | None]] = {"type": (True, None), "format": (True, None)}
            if not dry_run:
                prior_row = conn.execute(_SELECT_ARTICLE_FACETS_SQL, {"article_id": article_id}).fetchone()
                prior_type, prior_format = (prior_row[0], prior_row[1]) if prior_row else (None, None)
                facet_sync["type"] = _facet_sync_status(conn, entity_id, prior_type, terms, "type")
                facet_sync["format"] = _facet_sync_status(conn, entity_id, prior_format, terms, "format")

            # Only set for a facet this run actually changes (new accepted
            # value, or retracted to None); a facet not in this dict keeps
            # its `prior_type`/`prior_format` value untouched in the
            # combined UPDATE below.
            articles_update: dict[str, str | None] = {}

            # type + format + subtype: single-valued facets
            for dec, facet_key in ((r.type, "type"), (r.subtype, "subtype"), (r.format, "format")):
                uuid_ = term_uuid(terms, facet_key, dec.value)
                gate_clears = dec.auto_apply if dec.auto_apply is not None else dec.confidence >= AUTO_APPLY_AT_OR_ABOVE
                ok = gate_clears and uuid_ is not None
                if uuid_ is None and gate_clears:
                    stats.vocabulary_misses += 1
                if ok:
                    if facet_key == "type":
                        stats.type_accepted += 1
                    elif facet_key == "format":
                        stats.format_accepted += 1
                    else:
                        stats.subtype_accepted += 1
                    if not dry_run:
                        conn.execute(
                            _UPSERT_ENTITY_TERM_SQL,
                            {"entity_id": entity_id, "term_id": uuid_, "source": dec.source, "confidence": dec.confidence},
                        )
                        other_ids = _all_term_ids_for_facet(terms, facet_key)
                        if other_ids:
                            result = conn.execute(
                                _DELETE_STALE_FACET_TERMS_SQL,
                                {"entity_id": entity_id, "other_term_ids": other_ids, "keep_term_id": uuid_},
                            )
                            stats.stale_facet_terms_removed += result.rowcount
                        if facet_key in ("type", "format"):
                            in_sync, _reason = facet_sync[facet_key]
                            if in_sync:
                                articles_update[facet_key] = dec.value
                                stats.articles_facets_synced += 1
                            else:
                                stats.articles_facet_drift_skipped += 1
                else:
                    if facet_key == "type":
                        stats.type_reviewed += 1
                    elif facet_key == "format":
                        stats.format_reviewed += 1
                    else:
                        stats.subtype_reviewed += 1
                    if not dry_run:
                        _upsert_review(conn, article_id, facet_key, r.category_name, dec.value,
                                       dec.confidence, dec.reasoning, dec.source, site_slug,
                                       term_uuid(terms, facet_key, dec.value))
                        # This run has NOTHING to write for this facet (review,
                        # not accepted) -- retract any stale prior-run fact
                        # rather than let a debunked confidence sit alongside a
                        # fresh, honestly-lower-confidence review item. See
                        # `_DELETE_ALL_FACET_TERMS_SQL`'s docstring (wp_id 70).
                        all_ids = _all_term_ids_for_facet(terms, facet_key)
                        if all_ids:
                            result = conn.execute(
                                _DELETE_ALL_FACET_TERMS_SQL,
                                {"entity_id": entity_id, "term_ids": all_ids},
                            )
                            stats.stale_facet_terms_removed += result.rowcount
                        if facet_key in ("type", "format"):
                            in_sync, _reason = facet_sync[facet_key]
                            prior_value = prior_type if facet_key == "type" else prior_format
                            if in_sync and prior_value is not None:
                                # entity_terms just retracted its fact for this
                                # facet (F125) -- articles must not keep
                                # claiming a value entity_terms no longer
                                # backs. F132's "924 missing rows" shape.
                                articles_update[facet_key] = None
                                stats.articles_facets_synced += 1
                            elif not in_sync:
                                stats.articles_facet_drift_skipped += 1

            if not dry_run and articles_update:
                new_type = articles_update.get("type", prior_type)
                new_format = articles_update.get("format", prior_format)
                conn.execute(
                    _SET_ARTICLE_TYPE_FORMAT_SQL,
                    {"article_id": article_id, "primary_type": new_type, "format": new_format},
                )

            # location: multi-valued
            for dec in r.locations:
                uuid_ = term_uuid(terms, "location", dec.value)
                ok = dec.confidence >= AUTO_APPLY_AT_OR_ABOVE and uuid_ is not None
                if uuid_ is None and dec.confidence >= AUTO_APPLY_AT_OR_ABOVE:
                    stats.vocabulary_misses += 1
                if ok:
                    stats.location_accepted += 1
                    if not dry_run:
                        conn.execute(
                            _UPSERT_ENTITY_TERM_SQL,
                            {"entity_id": entity_id, "term_id": uuid_, "source": dec.source, "confidence": dec.confidence},
                        )
                else:
                    stats.location_reviewed += 1
                    if not dry_run:
                        _upsert_review(conn, article_id, "location", r.category_name, dec.value,
                                       dec.confidence, dec.reasoning, dec.source, site_slug, uuid_)
    return stats


def _upsert_review(conn, article_id: int, facet_key: str, legacy_category: str | None, proposed_value: str,
                    confidence: float, reasoning: str, source: str, site_slug: str, term_uuid_: str | None) -> None:
    existing = conn.execute(
        _FIND_PENDING_SQL,
        {"article_id": article_id, "facet_key": facet_key, "proposed_value": proposed_value},
    ).fetchone()
    params = {
        "legacy_category": legacy_category,
        "proposed_value": proposed_value,
        "confidence": confidence,
        "confidence_band": band(confidence),
        "reasoning": reasoning[:2000],
        "source": source,
    }
    if existing:
        conn.execute(_UPDATE_REVIEW_SQL, {**params, "id": existing[0]})
    else:
        new_id = conn.execute(
            _INSERT_REVIEW_SQL,
            {**params, "facet_key": facet_key, "term_id": term_uuid_, "site_slug": site_slug},
        ).scalar_one()
        conn.execute(_INSERT_REVIEW_REL_SQL, {"parent_id": new_id, "article_id": article_id})
