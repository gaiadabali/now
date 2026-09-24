"""Idempotent writes to `engine.entity_terms` for the six WS5 facets.

Source and confidence, and why this is safe to re-run and safe to remove
cleanly:

- `source = 'inferred'` -- the only value in `entity_terms_source_check`
  ('ai' | 'editor' | 'inferred') that isn't already claimed by a live
  producer for THESE SIX FACETS specifically. Verified live before this
  job ever wrote anything (see docs/EDITION-2-PLAN.md): `select count(*)
  from engine.entity_terms where term_id = any(<the 139 topic/audience/
  vibe/cuisine/price_band/occasion term ids>)` returned 0 in both
  `now_bali` and `now_jakarta` -- F137's "zero tagged articles" claim,
  independently confirmed, not just quoted. `inferred` IS already used
  heavily elsewhere (location's site-home-fallback, category-fixed
  locations, F125/F132's machinery) -- just never, before this job, for
  any of these six facets' term ids. That scoping (source='inferred' AND
  term_id = ANY(target_term_ids)) is what makes this job's rows
  unambiguously its own for re-run/removal purposes, without a schema
  change and without a new `source` value (the CHECK constraint is a
  senior-db/architect-owned migration this ticket does not take).
- `confidence` is the measured precision of the (facet, band) that
  produced the row -- `calibration.MEASURED_PRECISION` -- never an
  invented number, matching `now_classifier.confidence`'s own stated
  discipline.
- `weight = 1.0` -- these are independent single-signal proposals (a
  title-zone literal match, or price_band's cue instrument), not a
  blended multi-signal score; 1.0 matches every other producer's
  convention (`now_classifier.db._UPSERT_ENTITY_TERM_SQL`).
- Never overwrites an `editor` row (`... WHERE source <> 'editor'`, the
  same guard `now_classifier.db` uses) -- and since no `ai` row exists for
  these facets either, this guard is currently a formality, but it is the
  correct formality: an editor or a future `ai` producer for these facets
  must never be silently clobbered by a re-run of this job.
- Re-running RETRACTS a previously-written row that this run no longer
  proposes (code change, calibration revision, or the article's own text
  changed) -- scoped to `source = 'inferred' AND term_id = ANY(this
  facet's term ids)` for that one entity, so it can never touch a
  different facet's or a different producer's row. This mirrors F125's
  "entity_terms always reflects the LATEST run's decision" rule for
  type/format, applied here for the first time to these six facets.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Engine

_UPSERT_SQL = text(
    """
    insert into engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence)
    values ('article', :entity_id, cast(:term_id as uuid), 1.0, :source, :confidence)
    on conflict (entity_type, entity_id, term_id)
    do update set weight = excluded.weight, source = excluded.source, confidence = excluded.confidence
    where engine.entity_terms.source <> 'editor'
    """
)

# Retract a previously-written row for this (entity, facet) that this
# run no longer proposes. Scoped to `source` (the SAME producer that is
# doing the reconciling -- 'inferred' for the base job, 'ai' for
# `llm_refine`'s pass -- never 'editor', and never the OTHER producer's
# rows: the base job's retraction must not delete an LLM-refined row and
# vice versa) and to `facet_term_ids` (that one facet's term ids only) so
# a retraction for e.g. `vibe` can never delete a `cuisine` row.
_RETRACT_STALE_SQL = text(
    """
    delete from engine.entity_terms
    where entity_type = 'article' and entity_id = :entity_id
      and term_id = any(cast(:facet_term_ids as uuid[]))
      and term_id <> all(cast(:keep_term_ids as uuid[]))
      and source = :source
    """
)

_REMOVE_ALL_SQL = text(
    """
    delete from engine.entity_terms
    where entity_type = 'article'
      and term_id = any(cast(:term_ids as uuid[]))
      and source = :source
    """
)


@dataclass
class TagWriteStats:
    written: int = 0
    retracted: int = 0
    per_facet: dict[str, int] = field(default_factory=dict)


def write_tags(
    engine: Engine,
    proposals: dict[str, dict[str, dict[str, float]]],  # entity_id -> facet_key -> {term_id: confidence}
    facet_term_ids: dict[str, list[str]],        # facet_key -> ALL term ids for that facet (for retraction scope)
    dry_run: bool = False,
    source: str = "inferred",
) -> TagWriteStats:
    """`source` is 'inferred' for the base (non-LLM) job, 'ai' for
    `llm_refine`'s optional pass -- see this module's docstring for why
    those are the two producers this job uses, and why each one's
    reconciliation is scoped to only its own source."""
    stats = TagWriteStats()
    with engine.begin() as conn:
        for entity_id, by_facet in proposals.items():
            for facet_key, term_conf in by_facet.items():
                for term_id, confidence in term_conf.items():
                    stats.written += 1
                    stats.per_facet[facet_key] = stats.per_facet.get(facet_key, 0) + 1
                    if not dry_run:
                        conn.execute(
                            _UPSERT_SQL,
                            {"entity_id": entity_id, "term_id": term_id, "confidence": confidence, "source": source},
                        )
                if not dry_run:
                    result = conn.execute(
                        _RETRACT_STALE_SQL,
                        {
                            "entity_id": entity_id,
                            "facet_term_ids": facet_term_ids.get(facet_key, []),
                            "keep_term_ids": sorted(term_conf) or ["00000000-0000-0000-0000-000000000000"],
                            "source": source,
                        },
                    )
                    stats.retracted += result.rowcount
    return stats


def remove_all(engine: Engine, term_ids: list[str], dry_run: bool = False, source: str = "inferred") -> int:
    """Full removal of every row this job ever wrote (across all six
    facets, or a subset -- callers pass whichever `term_ids` they want
    gone) for the given `source` (default 'inferred', the base job;
    pass 'ai' to remove only `llm_refine`-written rows instead). Used by
    `now-classifier remove-facet-tags`."""
    if not term_ids:
        return 0
    if dry_run:
        with engine.connect() as conn:
            return conn.execute(
                text(
                    "select count(*) from engine.entity_terms where entity_type='article' "
                    "and term_id = any(cast(:term_ids as uuid[])) and source=:source"
                ),
                {"term_ids": term_ids, "source": source},
            ).scalar_one()
    with engine.begin() as conn:
        result = conn.execute(_REMOVE_ALL_SQL, {"term_ids": term_ids, "source": source})
        return result.rowcount
