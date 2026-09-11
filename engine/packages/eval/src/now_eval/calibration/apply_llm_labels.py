"""Wave 18, senior-be ticket 3 (T3) -- the LLM-batch APPLY step.

Reads the offline LLM batch's labels (`{city}_llm_labels.full.jsonl`,
written read-only by `batch_label.py`, F121) and replaces WEAK
machine-assigned `type`/`format` values in `engine.entity_terms` (and the
denormalized `public.articles.primary_type`/`.format` columns the runtime
engine actually queries -- ARCHITECTURE.md: "format drives decay
half-life", "primary_type drives competitor exclusion") with the LLM's
label, per `docs/llm-batch-apply-design.md` and F124/F125.

**This is the most dangerous writer in the project.** It overwrites live
values under a never-clobber-a-human invariant, against a table
(`engine.entity_terms`) that carries no protective DB trigger (F86 only
covers `public.classification_reviews`) and a table
(`public.articles`) that carries NO trigger AND no provenance column at
all for `primary_type`/`format` -- see "KNOWN SCHEMA GAP" below. Every
guard is therefore explicit in this module's own SQL and Python, never
assumed from the schema, per this ticket's brief.

--------------------------------------------------------------------------
Invariant 1 -- never overwrite a human decision
--------------------------------------------------------------------------
`engine.entity_terms.source` is the only signal (`CHECK (source IN ('ai',
'editor','inferred'))`, F86/QA.6). This module NEVER touches a
(article, facet) whose entity_terms rows include ANY `source='editor'`
row -- `plan_one`'s very first check -- and re-checks the same condition
again at write time under `SELECT ... FOR UPDATE` (`apply_change`), since
`engine-worker` can upsert `source='editor'` at any moment in response to
a live review decision, racing this batch.

--------------------------------------------------------------------------
Invariant 2 -- never overwrite a value the client has already reviewed
--------------------------------------------------------------------------
Per the design doc: the schema has no state distinct from "an editor
decided this" (`classification_reviews.review_state <> 'pending' AND
source = 'editor'`, or the identical `entity_terms.source = 'editor'`).
Rule 1's guard IS Rule 2's guard -- stated here again, not assumed
silently. This module never writes to `classification_reviews` at all (see
"OUT OF SCOPE" below), so a decided review row survives trivially (nothing
here can touch it), and F86's own DB trigger remains the backstop for that
table regardless.

--------------------------------------------------------------------------
Invariant 3 -- replace only what is weak
--------------------------------------------------------------------------
F125 stamps every auto-applied `entity_terms.confidence` at the MEASURED,
per-facet accuracy of the instrument that produced it
(`now_classifier.embed_routing.ROUTED_CONFIDENCE`, keyed `(band, facet)`).
Because entity_terms carries no `reasoning` column (unlike
`classification_reviews`), the only place that provenance marker survives
is the confidence NUMBER itself -- `band_for_confidence` reverses
`ROUTED_CONFIDENCE` to recover which band produced a given row's value,
per facet. This is exact-match, not fuzzy: F125's eight facet-scoped
constants (0.760/0.840/0.640/0.667 for type; 0.560/0.720/0.580/0.400 for
format) are all distinct from each other and from every other confidence
constant this project defines for type/format (see `LLM_BATCH_CONFIDENCE`
below), so the reverse lookup is unambiguous and doubles as this writer's
own idempotency check (a row this writer already replaced carries
`LLM_BATCH_CONFIDENCE`, which matches no band, and is therefore left
alone on a second run -- see "IDEMPOTENCY" below).

`is_low_accuracy_band` decides which bands are "weak enough to replace on
LLM disagreement":

  - **`format`: EVERY routed band, unconditionally.** This is the
    deliberate, disclosed choice F124 argues for, not a bug: even
    format's best-measured band (`category_fixed_high`, the old "0.95"
    label) measures only **0.560** -- F124's finding is that BOTH
    existing instruments (keyword cue, embeddings centroid) measure the
    wrong axis for format entirely (topic vocabulary vs. form/tense), so
    no format band is trustworthy regardless of its number, and F124
    adjudicated 142/142 in the LLM's favour on format specifically.
  - **`type`: only bands measuring below `TYPE_LOW_ACCURACY_MAX` (0.70).**
    Unlike format, F125's facet-scoped routing already picked the
    stronger instrument per band for type, and two of the four routed
    bands land materially above a coin flip
    (`cue_confident`=0.840, `category_fixed_high`=0.760) -- comparable to
    or better than F118's own pooled "not clearly weak enough to replace"
    reading of the old 0.95/0.75 bands (0.66/0.61). The other two
    (`category_fixed_medium`=0.640, `cue_fired`=0.667) sit clearly below
    that line. **0.70 is this ticket's own explicit threshold, chosen to
    fall in the real ~0.09 gap between 0.667 and 0.760** (there is no
    calibrated "correct" cutpoint here -- F113/F118 never measured type
    disagreement-replacement accuracy at intermediate thresholds -- so
    this is stated as a judgment call, not derived from data, exactly as
    this ticket's brief requires when a policy isn't fully specified).

Agreement (LLM value == current value) is always a no-op, checked AFTER
the band test so a no-op vs. "not eligible" is visible separately in the
dry-run report's skip reasons.

--------------------------------------------------------------------------
Invariant 4 -- the existing `public.articles` write path is untouched
--------------------------------------------------------------------------
`now_classifier.db`'s own write path is NOT imported, called, or modified
by this module. This module's own `_UPDATE_ARTICLES_TYPE_SQL` /
`_UPDATE_ARTICLES_FORMAT_SQL` are separate statements, gated on an
explicit `WHERE primary_type = :old_value` (optimistic-concurrency guard,
not a blind SET) -- see "KNOWN SCHEMA GAP".

**Update (F132, 2026-09-11):** `now_classifier.db.write_results`'s write
path changed after this module was written -- see that module's own F132
docstring. It no longer uses `coalesce(primary_type, ...)` ("set once from
NULL, never touched again"); that WAS the bug F132 found (~1,795 live
`articles`/`entity_terms` disagreements from the two stores having
different re-run semantics). It now uses `_facet_sync_status`, an
in-process proxy check with the identical shape this module's own
"KNOWN SCHEMA GAP" section below already invented independently: before
touching `articles`, confirm its current value still matches what
`entity_terms` held for that facet before this write. This module's own
guard (`articles_entity_terms_drift`, `WHERE primary_type = :old_value`)
is unaffected and still the one this module relies on -- it was written
without assuming anything about the classifier's internals, and that
remains true. Noted here only so a future reader does not treat this
paragraph's ORIGINAL "coalesce-only" description of `now_classifier.db`
as still accurate.

--------------------------------------------------------------------------
KNOWN SCHEMA GAP -- disclosed, not hidden (per this ticket's own brief)
--------------------------------------------------------------------------
`public.articles.primary_type`/`.format` have NO provenance column at all.
`engine/packages/cms/src/collections/Articles.ts` defines both fields as
plainly editable (`access.update: isAuthorOrAbove`, no `admin.readOnly`,
no companion `primaryTypeSource` field) -- a human CAN edit either field
directly in the CMS admin UI, completely outside the
classification_reviews / entity_terms flow, and nothing in the schema
records that this happened. (As of F132, `now_classifier.db`'s own write
path no longer relies on "never overwrites" for this protection either --
see Invariant 4's update above -- so this paragraph's original framing of
the classifier's coalesce-only path as the sole protection is no longer
current. The underlying gap this section describes is unchanged: no
schema column distinguishes a human edit from a machine write, for
EITHER writer.)

This module cannot manufacture that flag from a schema that does not have
it. Instead of describing a weaker guarantee as safe, it adds a concrete,
checkable proxy: **an article-facet is only ever touched if
`public.articles`'s current column value still equals what
`engine.entity_terms` says is the currently-accepted (non-editor) term's
slug** (`articles_entity_terms_drift` skip reason below). A mismatch is
common-cause evidence of exactly the gap above -- a direct CMS edit, a
missed sync, a bug -- and this module treats it as "possibly human,
definitely unexplained" and refuses the whole (article, facet), not just
the `public.articles` half of it. This closes the gap for THIS module's
blast radius (it cannot silently clobber a diverged value) but does not
retroactively prove any already-matching value was machine-set; a human
who directly edited `primary_type` to a value that happens to equal
`entity_terms`'s own value would not be protected. **The durable fix is a
migration** (out of this ticket's scope -- schema changes are
architect/senior-db owned): add `primary_type_source` /
`format_source enum('ai','inferred','editor') DEFAULT 'ai'` to
`public.articles`, stamped `'editor'` by a `beforeChange` hook on direct
admin edits (mirroring `autoPopulateOnDecision`'s `entity_terms`/
`classification_reviews` stamp), so a future writer can guard on it
directly instead of this consistency proxy. Flagged here, not implemented.

--------------------------------------------------------------------------
OUT OF SCOPE (v1) -- stated, not silently dropped
--------------------------------------------------------------------------
- Enriching still-`pending` `classification_reviews` rows with the LLM's
  opinion (the design doc's optional "MAY enrich... as a reviewer aid").
  Every additional write path is additional blast radius on the most
  dangerous ticket in the project; deferred as a separate, lower-risk
  follow-up. This module contains NO SQL against `classification_reviews`
  at all (statically verified, see the test suite).
- `subtype`/`location`: F124/F121/the design doc scope this apply step to
  type/format only (the two facets the LLM batch actually labels per
  call -- `llm_client.build_prompt` asks for exactly `type`+`format`).

--------------------------------------------------------------------------
Read-only against `now_jakarta`/`now_bali`, always, in this module
--------------------------------------------------------------------------
`LIVE_CITY_DBS` is a hard-coded refusal list. `run_apply(..., dry_run=False)`
raises `RefusedLiveWriteError` before opening a single write transaction if
the resolved db_ref for ANY requested city is in that set. Dry-run mode
(`dry_run=True`, the default) issues SELECTs only -- proven by
`test_apply_llm_labels_readonly.py`'s before/after row-count diff against
the real `now_jakarta`/`now_bali`.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

FACETS: tuple[str, ...] = ("type", "format")
CITY_DB = {"jakarta": "now_jakarta", "bali": "now_bali"}
LIVE_CITY_DBS = frozenset({"now_jakarta", "now_bali"})

# Deliberately distinct from every ROUTED_CONFIDENCE value (0.760, 0.840,
# 0.640, 0.667 for type; 0.560, 0.720, 0.580, 0.400 for format) and from
# every other type/format confidence constant this project defines
# (confidence.py: 0.95/0.93/0.90/0.75/0.72/0.70/0.45/0.40/0.35). Chosen,
# not derived: F118/F124's own evidence (211/211, then 142/142
# format-specific) is a disagreement-conditioned rate, not a population
# accuracy -- see the module docstring's "known limitation" note carried
# over from docs/llm-batch-apply-design.md -- so this number is a
# deliberately distinguishable SENTINEL for "this value came from the LLM
# batch apply step", not a claim that 0.86 is this instrument's measured
# real-world accuracy. Doubles as the idempotency marker: a row already at
# this confidence matches no `ROUTED_CONFIDENCE` band, so `band_for_confidence`
# returns None and a second run leaves it alone (`unrecognized_provenance`).
LLM_BATCH_CONFIDENCE = 0.86
LLM_BATCH_SOURCE = "ai"  # entity_terms.source CHECK only allows ai/editor/inferred -- 'editor' would
                         # be a lie (no human reviewed this), 'inferred' already means something else
                         # (category-prior fallback) elsewhere in this codebase. Recommended follow-up
                         # (migration, out of scope here): widen the CHECK to add 'llm_batch' so this
                         # provenance is legible without needing the confidence-value convention above.

# F125's own facet-scoped threshold for "not clearly weak enough to
# replace" landed type's four routed bands at 0.640/0.667/0.760/0.840.
# This ticket's own choice (not measured, disclosed as such -- see module
# docstring): bands strictly below this are "low accuracy" for type.
TYPE_LOW_ACCURACY_MAX = 0.70


# ==========================================================================
# Pure logic -- no DB, no network. Unit-tested directly.
# ==========================================================================

@dataclass(frozen=True)
class LlmLabel:
    city: str
    wp_id: int
    type: str | None
    format: str | None
    error: str | None
    type_reasoning: str = ""
    format_reasoning: str = ""

    def value_for(self, facet: str) -> str | None:
        return self.type if facet == "type" else self.format

    def reasoning_for(self, facet: str) -> str:
        return self.type_reasoning if facet == "type" else self.format_reasoning


@dataclass(frozen=True)
class TermRow:
    term_id: str
    slug: str
    source: str
    confidence: float


@dataclass(frozen=True)
class FacetState:
    """Current live state of one (city, article, facet), as read from the
    city DB. `rows` is EVERY `engine.entity_terms` row for this article
    whose `term_id` belongs to this facet's vocabulary -- deliberately not
    pre-filtered by source, so `plan_one` can apply Invariant 1 itself
    rather than trusting an upstream filter."""
    city: str
    wp_id: int
    article_id: int
    facet: str
    rows: tuple[TermRow, ...]
    articles_column_value: str | None


def is_low_accuracy_band(facet: str, band: str) -> bool:
    from now_classifier.embed_routing import ROUTED_CONFIDENCE

    if facet == "format":
        # F124: format's best-measured band (category_fixed_high) is 0.560
        # -- the LLM supersedes every machine band for format, deliberately,
        # per F124's "let the LLM own format" recommendation. Still require
        # the band to be a real, routed one (see band_for_confidence) --
        # this is not "always true", it's "true for every band F125 routes".
        return (band, "format") in ROUTED_CONFIDENCE
    if facet == "type":
        acc = ROUTED_CONFIDENCE.get((band, "type"))
        if acc is None:
            return False
        return acc < TYPE_LOW_ACCURACY_MAX
    raise ValueError(f"unknown facet {facet!r}")


def band_for_confidence(facet: str, confidence: float) -> str | None:
    """Reverses F125's `ROUTED_CONFIDENCE` (band, facet) -> measured
    accuracy table to recover which band produced a given entity_terms
    row's confidence value. Exact match at the numeric(5,4) precision the
    column is stored at -- returns None (not a routed band; could be an
    already-LLM-replaced row, a pre-F125 legacy value, or something this
    module was never told about) if nothing matches. Callers MUST treat
    None as "leave alone", never as a default band -- that is what makes
    this module idempotent (see LLM_BATCH_CONFIDENCE's docstring)."""
    from now_classifier.embed_routing import ROUTED_CONFIDENCE

    target = round(float(confidence), 4)
    for (band, band_facet), acc in ROUTED_CONFIDENCE.items():
        if band_facet == facet and round(acc, 4) == target:
            return band
    return None


@dataclass(frozen=True)
class PlannedChange:
    city: str
    wp_id: int
    article_id: int
    facet: str
    old_term_id: str
    old_slug: str
    old_confidence: float
    band: str
    new_slug: str
    new_term_id: str
    llm_reasoning: str


@dataclass(frozen=True)
class Skip:
    city: str
    wp_id: int
    facet: str
    reason: str
    detail: str = ""


def plan_one(state: FacetState, label: LlmLabel | None, term_uuid_fn) -> PlannedChange | Skip:
    """Pure decision function: given the article-facet's current DB state
    and the LLM's (possibly absent) label, decide replace / leave alone.
    `term_uuid_fn(facet, slug) -> uuid|None` is injected (not imported
    directly) so this stays testable without a real TermIndex/DB."""
    editor_rows = [r for r in state.rows if r.source == "editor"]
    non_editor_rows = [r for r in state.rows if r.source != "editor"]

    if editor_rows:
        # Invariant 1/2: a human decision exists for this facet -- do not
        # touch it, and do not touch any OTHER row sitting alongside it
        # either (safer than trying to disentangle a mixed state).
        return Skip(state.city, state.wp_id, state.facet, "editor_sourced_present",
                    f"{len(editor_rows)} editor row(s) present")
    if not non_editor_rows:
        # Never auto-applied to begin with (still in classification_reviews,
        # or genuinely unresolved) -- not this step's target (design doc:
        # "not an auto-apply target at all").
        return Skip(state.city, state.wp_id, state.facet, "no_entity_terms_row")
    if len(non_editor_rows) > 1:
        # Should not happen post-F125 (stale-fact retraction fixed this
        # class of bug) -- fail closed rather than guess which row is live.
        return Skip(state.city, state.wp_id, state.facet, "ambiguous_multiple_rows",
                    f"{len(non_editor_rows)} non-editor rows")
    row = non_editor_rows[0]

    band = band_for_confidence(state.facet, row.confidence)
    if band is None:
        return Skip(state.city, state.wp_id, state.facet, "unrecognized_provenance",
                    f"confidence={row.confidence}")
    if not is_low_accuracy_band(state.facet, band):
        return Skip(state.city, state.wp_id, state.facet, "not_low_accuracy_band", band)

    if label is None:
        return Skip(state.city, state.wp_id, state.facet, "llm_missing")
    if label.error:
        return Skip(state.city, state.wp_id, state.facet, "llm_error", label.error)
    llm_value = label.value_for(state.facet)
    if not llm_value:
        return Skip(state.city, state.wp_id, state.facet, "llm_missing_value")

    if state.articles_column_value != row.slug:
        # KNOWN SCHEMA GAP guard (module docstring): public.articles has
        # drifted from entity_terms's own accepted value -- unexplained,
        # possibly a direct human edit. Refuse the whole article-facet.
        return Skip(state.city, state.wp_id, state.facet, "articles_entity_terms_drift",
                    f"articles={state.articles_column_value!r} entity_terms={row.slug!r}")

    if llm_value == row.slug:
        return Skip(state.city, state.wp_id, state.facet, "llm_agrees")

    new_term_id = term_uuid_fn(state.facet, llm_value)
    if new_term_id is None:
        return Skip(state.city, state.wp_id, state.facet, "llm_vocabulary_miss", llm_value)

    return PlannedChange(
        city=state.city, wp_id=state.wp_id, article_id=state.article_id, facet=state.facet,
        old_term_id=row.term_id, old_slug=row.slug, old_confidence=row.confidence, band=band,
        new_slug=llm_value, new_term_id=new_term_id,
        llm_reasoning=label.reasoning_for(state.facet),
    )


def plan_all(states: Iterable[FacetState], labels_by_key: dict[tuple[str, int], LlmLabel], term_uuid_fn
             ) -> tuple[list[PlannedChange], list[Skip]]:
    planned: list[PlannedChange] = []
    skipped: list[Skip] = []
    for state in states:
        label = labels_by_key.get((state.city, state.wp_id))
        result = plan_one(state, label, term_uuid_fn)
        if isinstance(result, PlannedChange):
            planned.append(result)
        else:
            skipped.append(result)
    return planned, skipped


def build_dry_run_report(planned: list[PlannedChange], skipped: list[Skip], sample_size: int = 10) -> dict:
    """The diff report Hansel approves against: rows to change, grouped by
    city/facet/provenance band, with a bounded sample -- plus every skip
    reason, so "nothing happened for article X" is never invisible."""
    from now_classifier.embed_routing import ROUTED_CONFIDENCE

    by_group: dict[tuple[str, str, str], list[PlannedChange]] = defaultdict(list)
    for p in planned:
        by_group[(p.city, p.facet, p.band)].append(p)

    changes_by_group = []
    for (city, facet, band), changes in sorted(by_group.items()):
        changes_by_group.append({
            "city": city, "facet": facet, "band": band,
            "measured_accuracy_replaced": ROUTED_CONFIDENCE.get((band, facet)),
            "count": len(changes),
            "sample": [
                {"wp_id": c.wp_id, "old": c.old_slug, "new": c.new_slug, "llm_reasoning": c.llm_reasoning}
                for c in changes[:sample_size]
            ],
        })

    skip_counts = Counter((s.city, s.facet, s.reason) for s in skipped)
    skip_summary = [
        {"city": city, "facet": facet, "reason": reason, "count": n}
        for (city, facet, reason), n in sorted(skip_counts.items())
    ]

    return {
        "total_articles_facets_examined": len(planned) + len(skipped),
        "total_planned_changes": len(planned),
        "total_skipped": len(skipped),
        "changes_by_city_facet_band": changes_by_group,
        "skip_reasons": skip_summary,
    }


class RefusedLiveWriteError(RuntimeError):
    def __init__(self, live_dbs: set[str]) -> None:
        super().__init__(
            f"refusing to write: {sorted(live_dbs)} is/are in LIVE_CITY_DBS -- "
            "this ticket's scope is dry-run + now_test/scratch only. Pass a non-live db_ref "
            "(e.g. now_test) to actually execute, or dry_run=True to plan against real data safely."
        )
        self.live_dbs = live_dbs


# ==========================================================================
# I/O: DB reads (entity_terms + public.articles), ledger reads, DB writes.
# ==========================================================================

def load_llm_labels(path: Path) -> dict[int, LlmLabel]:
    """One city's ledger file -> wp_id -> LlmLabel. Any line missing
    type/format or carrying an `error` is still loaded (plan_one handles
    both explicitly, distinctly from a missing label) -- never silently
    dropped."""
    out: dict[int, LlmLabel] = {}
    if not path.is_file():
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            out[int(row["wp_id"])] = LlmLabel(
                city=row["city"], wp_id=int(row["wp_id"]),
                type=row.get("type"), format=row.get("format"),
                error=row.get("error"),
                type_reasoning=row.get("type_reasoning", ""),
                format_reasoning=row.get("format_reasoning", ""),
            )
    return out


def _facet_term_ids(terms, facet: str) -> list[str]:
    return [uuid_ for uuid_, _parent in terms.by_facet.get(facet, {}).values()]


def _slug_for_term_id(terms, facet: str, term_id: str) -> str | None:
    for slug, (uuid_, _parent) in terms.by_facet.get(facet, {}).items():
        if uuid_ == term_id:
            return slug
    return None


def read_facet_states(engine, terms, city: str, facet: str) -> list[FacetState]:
    """Read-only. One SELECT against `public.articles` (id/legacy_wp_id/
    primary_type/format) and one against `engine.entity_terms` (scoped to
    this facet's term-id set), joined in Python -- same two-query shape
    `now_eval.calibration.db_frame` already uses for read-only reporting,
    reused here because it is the established, reviewed pattern for this
    exact join, not because this module imports db_frame (it doesn't --
    db_frame is calibration-sampling-shaped, this is apply-shaped)."""
    from sqlalchemy import text

    term_ids = _facet_term_ids(terms, facet)
    if not term_ids:
        return []
    column = "primary_type" if facet == "type" else "format"

    with engine.connect() as conn:
        articles = conn.execute(
            text(f"select id, legacy_wp_id, {column}::text as val from public.articles where legacy_wp_id is not null")
        ).fetchall()
        article_by_id = {int(aid): (int(wp), val) for aid, wp, val in articles}

        term_rows = conn.execute(
            text(
                """
                select entity_id::int as article_id, term_id::text as term_id, source, confidence
                from engine.entity_terms
                where entity_type = 'article' and term_id = any(cast(:term_ids as uuid[]))
                """
            ),
            {"term_ids": term_ids},
        ).fetchall()

    rows_by_article: dict[int, list[TermRow]] = defaultdict(list)
    for article_id, term_id, source, confidence in term_rows:
        if article_id not in article_by_id:
            continue
        slug = _slug_for_term_id(terms, facet, term_id)
        if slug is None:
            continue
        rows_by_article[article_id].append(
            TermRow(term_id=term_id, slug=slug, source=source, confidence=float(confidence))
        )

    out: list[FacetState] = []
    for article_id, (wp_id, articles_value) in article_by_id.items():
        out.append(FacetState(
            city=city, wp_id=wp_id, article_id=article_id, facet=facet,
            rows=tuple(rows_by_article.get(article_id, [])),
            articles_column_value=articles_value,
        ))
    return out


@dataclass(frozen=True)
class ApplyResult:
    change: PlannedChange
    ok: bool
    reason: str


def apply_change(engine, change: PlannedChange, facet_term_ids: list[str]) -> ApplyResult:
    """Executes exactly ONE (article, facet) replacement, inside its own
    transaction, per `docs/llm-batch-apply-design.md`'s transaction shape:
    `SELECT ... FOR UPDATE` re-check -> DELETE old term (source-guarded) ->
    INSERT new term -> guarded UPDATE public.articles. Any inconsistency
    detected at write time (a race with a concurrent editor decision, or
    with a direct CMS edit to `public.articles`) aborts ONLY this one
    change (the transaction rolls back) rather than the whole batch."""
    from sqlalchemy import text

    select_for_update = text(
        """
        select term_id::text, source, confidence
        from engine.entity_terms
        where entity_type = 'article' and entity_id = :entity_id
          and term_id = any(cast(:term_ids as uuid[]))
        for update
        """
    )
    delete_old = text(
        """
        delete from engine.entity_terms
        where entity_type = 'article' and entity_id = :entity_id
          and term_id = :old_term_id and source <> 'editor'
        """
    )
    insert_new = text(
        """
        insert into engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence)
        values ('article', :entity_id, cast(:new_term_id as uuid), 1.0, :source, :confidence)
        """
    )
    column = "primary_type" if change.facet == "type" else "format"
    enum_type = "enum_articles_primary_type" if change.facet == "type" else "enum_articles_format"
    update_articles = text(
        f"""
        update public.articles
        set {column} = cast(:new_value as {enum_type})
        where id = :article_id and {column} = cast(:old_value as {enum_type})
        """
    )

    entity_id = str(change.article_id)
    with engine.begin() as conn:
        rows = conn.execute(select_for_update, {"entity_id": entity_id, "term_ids": facet_term_ids}).fetchall()
        editor_rows = [r for r in rows if r[1] == "editor"]
        non_editor_rows = [r for r in rows if r[1] != "editor"]
        if editor_rows:
            return ApplyResult(change, False, "race_editor_appeared")
        if len(non_editor_rows) != 1 or non_editor_rows[0][0] != change.old_term_id:
            return ApplyResult(change, False, "race_state_changed")
        _, _source, confidence = non_editor_rows[0]
        band = band_for_confidence(change.facet, float(confidence))
        if band is None or not is_low_accuracy_band(change.facet, band):
            return ApplyResult(change, False, "race_no_longer_eligible")

        deleted = conn.execute(delete_old, {"entity_id": entity_id, "old_term_id": change.old_term_id}).rowcount
        if deleted != 1:
            raise RuntimeError(
                f"expected to delete exactly 1 entity_terms row for article_id={change.article_id} "
                f"facet={change.facet}, deleted {deleted} -- aborting this change's transaction"
            )
        conn.execute(insert_new, {
            "entity_id": entity_id, "new_term_id": change.new_term_id,
            "source": LLM_BATCH_SOURCE, "confidence": LLM_BATCH_CONFIDENCE,
        })
        updated = conn.execute(update_articles, {
            "article_id": change.article_id, "new_value": change.new_slug, "old_value": change.old_slug,
        }).rowcount
        if updated != 1:
            raise RuntimeError(
                f"public.articles.{column} for article_id={change.article_id} no longer equalled "
                f"{change.old_slug!r} at write time (concurrent CMS edit?) -- aborting this change's transaction"
            )
    return ApplyResult(change, True, "applied")


@dataclass
class ApplyReport:
    dry_run: bool
    planned: list[PlannedChange] = field(default_factory=list)
    skipped: list[Skip] = field(default_factory=list)
    applied: list[ApplyResult] = field(default_factory=list)

    def summary(self) -> dict:
        d = build_dry_run_report(self.planned, self.skipped)
        d["dry_run"] = self.dry_run
        if not self.dry_run:
            d["applied_ok"] = sum(1 for a in self.applied if a.ok)
            d["applied_failed"] = sum(1 for a in self.applied if not a.ok)
            failed_reasons = Counter(a.reason for a in self.applied if not a.ok)
            d["applied_failed_reasons"] = dict(failed_reasons)
        return d


def run_apply(
    cities: tuple[str, ...],
    ledger_dir: Path,
    terms,
    *,
    city_db_map: dict[str, str] = CITY_DB,
    engine_factory=None,
    dry_run: bool = True,
) -> ApplyReport:
    """Orchestrator. `engine_factory(db_ref) -> sqlalchemy Engine` is
    injected (default: `now_classifier.db.make_engine`) so tests can point
    it at `now_test` or a scratch DB. Refuses outright (before any DB call
    that could write) if `dry_run=False` and any requested city resolves
    to a `LIVE_CITY_DBS` entry."""
    if engine_factory is None:
        from now_classifier.db import make_engine as engine_factory

    if not dry_run:
        live = {city_db_map[c] for c in cities if city_db_map.get(c) in LIVE_CITY_DBS}
        if live:
            raise RefusedLiveWriteError(live)

    def term_uuid_fn(facet: str, slug: str) -> str | None:
        from now_classifier.vocabulary import term_uuid
        return term_uuid(terms, facet, slug)

    all_planned: list[PlannedChange] = []
    all_skipped: list[Skip] = []
    engines: dict[str, object] = {}
    for city in cities:
        db_ref = city_db_map[city]
        engines[city] = engine_factory(db_ref)
        ledger_path = ledger_dir / f"{city}_llm_labels.full.jsonl"
        labels = load_llm_labels(ledger_path)
        labels_by_key = {(city, wp_id): label for wp_id, label in labels.items()}
        for facet in FACETS:
            states = read_facet_states(engines[city], terms, city, facet)
            planned, skipped = plan_all(states, labels_by_key, term_uuid_fn)
            all_planned.extend(planned)
            all_skipped.extend(skipped)

    applied: list[ApplyResult] = []
    if not dry_run:
        for change in all_planned:
            engine = engines[change.city]
            applied.append(apply_change(engine, change, _facet_term_ids(terms, change.facet)))

    return ApplyReport(dry_run=dry_run, planned=all_planned, skipped=all_skipped, applied=applied)
