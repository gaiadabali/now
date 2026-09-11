# LLM batch labels — apply-step design (NOT implemented in this ticket)

Wave 18, senior-be ticket 2. This document specifies precisely how the
labels written by `now_eval.calibration.batch_label` (to
`engine/packages/eval/data/llm_batch/{city}_llm_labels.full.jsonl`) are
meant to be applied later, once Hansel decides to run it. **Nothing in
this ticket runs this step.** The batch labeller itself is read-only
against both city DBs (proven in the ticket report); this design exists so
the apply step, whenever it is built, does not have to re-derive these
rules from scratch — and so it can be reviewed before any code against it
is written.

## Why apply is a separate, later, human-gated step

1. The routing agent's best-of-band work (Wave 18 ticket 1) is running
   concurrently and re-classifying both cities right now. Applying LLM
   labels against a moving target would race it. Apply only after that
   work is confirmed complete and stable.
2. Applying is a write against `now_jakarta`/`now_bali` — squarely
   schema/DDL-adjacent territory (touches `engine.entity_terms` and
   `public.classification_reviews` row-level data, not DDL, but still a
   production write path) and per this seat's own rules should get an
   architect/senior-db sanity check on the exact queries before it runs
   against real rows, not just this design doc.
3. Most importantly: the two safety rules below are about **not being
   able to undo damage** if they are violated. Getting them right matters
   more than getting them soon.

## The two rules that must never be violated

### Rule 1 — never overwrite a human decision

**`public.classification_reviews`** (Payload-owned, `public` schema):
already enforced at the DB by migration `20260910_060000_classification_reviews_no_clobber_trigger`
(F86). Once a row's `review_state <> 'pending'` under `source = 'editor'`,
any `UPDATE` that does not itself assert `source = 'editor'` is rejected
outright (`classification_reviews_no_clobber` trigger, `RAISE EXCEPTION`,
`ERRCODE = 'restrict_violation'`). An apply step driven by this batch's
output will always write with `source` left at its automated default
(never spoofing `'editor'`), so this trigger is a real backstop, not
theatre — but the apply step should still **filter proactively** (query
`WHERE review_state = 'pending'`) rather than rely on catching the
exception on every already-decided row; the trigger is defense in depth,
not the primary filter.

**`engine.entity_terms`** (engine-owned, DB-per-city, no Payload access):
confirmed via `engine/packages/db/.../0001_baseline_engine_schema.py` —
**no trigger, rule, or constraint protects an editor-sourced row.** The
only guard is `source` itself (`CHECK (source IN ('ai','editor','inferred'))`,
default `'ai'`), and only if the *writer's query* remembers to test it.
QA.6 demonstrated exactly this gap being exploitable (F86's own finding).
**The apply step MUST include `AND source <> 'editor'` in every predicate
that selects rows to replace, with no exceptions**, because nothing else
will stop it. This is not this ticket's DDL to add — F86 deliberately
scoped the DB-level fix to `classification_reviews` only, leaving
`entity_terms`'s protection as an application-level discipline
(`engine-worker`'s own upsert already follows it: `WHERE source <>
'editor'`, per the F86 migration's own description) that every future
writer, including this apply step, must repeat.

Concretely, because `entity_terms`'s primary key is
`(entity_type, entity_id, term_id)` — the *term itself* is part of the
key, not a value column — replacing a type/format value is a
delete-old-term-row + insert-new-term-row operation, not a column
`UPDATE`. The apply step's transaction per article must be:

```sql
-- inside one transaction, per (city, entity_id, facet):
SELECT source FROM engine.entity_terms
 WHERE entity_type = 'article' AND entity_id = :entity_id
   AND term_id IN (SELECT id FROM <platform>.engine.terms WHERE facet_id = <facet>)
 FOR UPDATE;
-- if source = 'editor' -> STOP, do not touch this article's this facet, at all.
-- else:
DELETE FROM engine.entity_terms
 WHERE entity_type = 'article' AND entity_id = :entity_id
   AND term_id = :old_term_id AND source <> 'editor';
INSERT INTO engine.entity_terms (entity_type, entity_id, term_id, source, confidence, created_at)
 VALUES ('article', :entity_id, :new_term_id, 'ai', :measured_confidence, now());
```

The `SELECT ... FOR UPDATE` + re-checked `source <> 'editor'` on the
`DELETE` is belt-and-braces against a race with a concurrent editor
decision landing between the read and the write — a real possibility
since `engine-worker` can upsert `source='editor'` at any time in
response to a live review decision.

### Rule 2 — never overwrite a value the client has already reviewed

Nothing in the schema distinguishes "an internal editor decided this"
from "Hansel's client-facing final pass approved this" — both go through
the same `classification-reviews` → `autoPopulateOnDecision` →
`source='editor'` path (`reviewQueueHooks.ts`), and the same
`engine-worker` upsert into `entity_terms` with `source='editor'`. **This
is not a gap to fix — it means Rule 1's guard (`source <> 'editor'`,
`review_state = 'pending'`) already *is* Rule 2's guard.** "The client
reviewed this" and "an editor decided this" are the same fact in the data
model today. If a genuinely separate client-approval state is ever added
(e.g. a `client_approved` flag distinct from `reviewState`), this design
must be revisited — the apply step's predicate would need to OR in that
new condition. Until then, treating `source = 'editor'` as "hands off,
permanently" satisfies both rules with one guard, and that is
deliberate, not an oversight.

### The corollary: no auto-apply into entity_terms at all, in v1

Given Rule 1 needs `source <> 'editor'` and Rule 2 collapses into Rule 1,
the safe subset of `entity_terms` rows this step may ever touch is
exactly `source IN ('ai', 'inferred')` — i.e. never-yet-reviewed,
auto-applied values. That is deliberately conservative: it is also
**every row currently in `entity_terms`**, so there is no dead code here,
just a live invariant the apply step must keep re-checking at write time
(state changes underneath it while it runs, hence the `FOR UPDATE`
re-check above), not just once at read time.

## Which values get replaced, and which are left alone

The routing agent (Wave 18 ticket 1) is stamping every auto-applied value
with **measured confidence + instrument provenance** — replacing the old
invented 0.95/0.93/0.75/0.72 numbers that F96/F111/F113 established meant
nothing. This batch's apply step depends on that landing first, and reads
it, rather than re-deriving band membership itself:

- **Replace** an `entity_terms` row's value with the LLM's label when
  ALL of:
  1. `source <> 'editor'` (Rule 1/2, re-checked at write time), AND
  2. the row's measured-accuracy/provenance marker (from the routing
     agent's work) says this value came from a **low-accuracy band** —
     concretely, anything at or below the `0.93` band's measured **0.45**
     accuracy, and the `0.72`/abstain bands below that (F113: 0.283,
     0.417, 0.312) — NOT the `0.95` band (0.66) or `0.75` band (0.61),
     which, while still short of the invented 0.85 gate, are not where a
     replacement clearly pays for itself against this batch's own
     accuracy (F118: 211/211 on contested cases, but that is a sample of
     *disagreements* — see "known limitation" below), AND
  3. the LLM's `type`/`format` differs from the current value (agreement
     is a no-op — don't burn a write on confirming what's already there).
- **Leave alone, unconditionally**: anything with `source = 'editor'`,
  regardless of band, confidence, or LLM (dis)agreement. No exceptions.
- **Leave alone**: anything the LLM itself returned an `error` for (retry
  in a later batch run, don't apply a null label).
- **`classification_reviews` rows still `review_state = 'pending'`**: not
  an auto-apply target at all (they're already gated behind a human).
  The apply step MAY enrich these rows' `proposedValue` /
  `confidenceBand` / `reasoning` with the LLM's opinion, as a
  reviewer aid, since the F86 trigger permits free writes to pending rows
  — but this is a UX improvement for whoever reviews the queue, never a
  bypass of the human gate, and finalValue/reviewState must never be
  touched by an automated writer (only `autoPopulateOnDecision`,
  triggered by an actual editor action, sets those).

**Known limitation, stated plainly:** F118's 211/211 evidence comes from
a *disagreement-enriched* adjudication sample (PROVENANCE.md §8.2/8.4),
not a random sample of the whole corpus — it shows the LLM beats the
classifier when they disagree, not what fraction of the full corpus that
covers. The apply step's replace-only-on-disagreement rule follows
directly from that evidence's actual shape (it says nothing about cases
where the two already agree, so those are correctly left as no-ops
above), but this is exactly the same caveat F118/F120 have both been
careful to name for the classifier and embeddings measurements. If Hansel
wants a fresh random-sample check specifically on this batch's output
before a real apply run, that is a cheap follow-up (a few dozen
adjudications), not a blocker to writing this design now.

## Idempotency and dry-run

The apply step (whenever built) must support `--dry-run` (print every
intended write, make none) as a first-class mode, and must be safe to
re-run: since it always re-checks `source <> 'editor'` at write time and
skips on LLM/current-value agreement, running it twice against the same
ledger produces the same end state, not compounding writes.

## What this ticket did NOT build

No code implementing any of the above exists yet. `batch_label.py`
contains no INSERT/UPDATE/DELETE against any database (statically
verified by `tests/calibration/test_batch_label.py::test_batch_label_module_contains_no_write_sql`).
Building the apply step is separate follow-on work, gated on: (a) the
routing agent's provenance-stamping work landing, (b) an architect/
senior-db review of the exact transaction shape above against the real
schema, and (c) Hansel's go-ahead to run it.
