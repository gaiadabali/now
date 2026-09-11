# Vocabulary retirement playbook

Design document only — **no code in this file, and this file authorises no execution**. It exists
because F89 proved that retiring a term from the shared taxonomy (`now_platform.engine.terms`) is
one of the most hostile operations in this codebase, and because F124 (PROGRESS.md) needed a real
follow-up (T6) once its `format` investigation raised the question of whether any of the 11
`format` terms should ever be retired. **Nothing here retires a term** — F124's own recommendation
was "keep all 11 terms, no enum migration, let the LLM own `format`" — this document is the
procedure for the day a term genuinely does need to go.

Read this before touching `engine.terms`, a Payload enum `select` field, or running
`payload migrate:create` on a collection whose options come from the shared vocabulary.

---

## 1. Why this is hard: the F89 landmine

`cms/src/lib/vocabulary.ts` builds each facet `select` field's `options` array from
`now_platform.engine.terms` **once, at CMS process boot** (module load, before `buildConfig`
runs — see the module's own docstring). Those same options are also what
`payload migrate:create` diffs against when it decides whether the underlying Postgres ENUM
needs to change: it computes the *target* schema from the **current** vocabulary and compares it
to the **snapshot** baked into the last generated migration.

F89's finding, reproduced deliberately by E2.0c to prove the risk was real (the migration was
generated, confirmed, then deleted — never applied): once a term (`rawamangun`) left
`engine.terms`, the very next `migrate:create` proposed **recreating** the enum type
(`enum_places_area_term`) without it. Postgres has no `ALTER TYPE ... DROP VALUE`, so Payload's
generator falls back to the only thing it knows how to diff: drop-and-recreate the type. That is
a destructive type-recreation, and — this is the part that makes it a *standing* landmine, not a
one-off — **it keeps proposing the same recreation on every future `migrate:create` run** until
someone regenerates the drizzle snapshot to match. F89's root cause, in its own words: Payload
has *"no notion of permanently retired but not forgotten."*

Soft-retire (§2) is the direct fix for that gap: never let a term actually leave
`engine.terms`, and never let it leave the Payload options array, so drizzle's target computation
and its stored snapshot never diverge and there is nothing to diff.

---

## 2. Soft-retire — the default pattern

Use this unless a specific, named reason forces §3. Steps, roughly in order:

1. **Migrate the data first.** Every city-DB row currently carrying the retiring term (in
   `entity_terms`, `classification_reviews`, or any other referencing column — see §4's
   `check-term-refs` gate) is moved to its replacement term or otherwise resolved. Nothing keeps
   pointing at the retired value once this step is done, except possibly historical
   snapshot/audit rows that are explicitly out of scope (e.g. `classification_reviews` rows that
   record what the AI *originally proposed* are a durable historical record, not a live
   reference — see `now_db.term_refs`'s module docstring for that distinction).
2. **Keep the enum label in Postgres.** Do not drop the value from the Postgres ENUM type. It
   becomes a harmless zombie: a legal value nothing is ever written into again.
3. **Keep the option in Payload's `select` field**, so the CMS options array Payload computes
   from `engine.terms` still contains it — this is the crux of the fix. Because the option is
   still present, `drizzle`'s target-computed schema still matches the snapshot: **no diff, no
   landmine.** Label it `"(retired)"` in the option's display label so editors can see it is not a
   live choice, and reject it in the field's `validate` function so no document can newly be
   saved with that value (existing documents that still carry it — if any slipped through step 1
   — continue to load and render; `validate` only gates new writes).
4. **Set `engine.terms.attrs.retired_at`** on the term's row in `now_platform.engine.terms` (an
   ISO timestamp). This column has been writable since F88 fixed `_UPSERT_TERM`/`SeedTerm` to
   actually read and write `attrs` — before that fix `attrs` was silently write-inert (see F88 and
   the seed-file caveat in §5). `retired_at` is the single flag every consumer below keys off.
5. **Exclude retired terms from the classifier and LLM vocabularies.** Any code path that builds a
   candidate-term list for the classifier (cue lexicon, embeddings centroid roster) or for the
   LLM batch prompt (e.g. `now_eval.calibration.llm_client.FORMAT_DESCRIPTIONS`-style constants)
   must filter out any term with `attrs.retired_at` set, so a retired term is never proposed again
   even though it is still a legal value in the schema.
6. **Zero enum DDL.** No `ALTER TYPE`, no migration file, nothing for Payload's generator to
   diff. This is the whole point: the enum, the Payload options, and the drizzle snapshot all
   still agree, because nothing left any of them.

Net effect: the term becomes inert everywhere a human or a model would newly choose it, while
remaining structurally present everywhere the schema would otherwise force a destructive diff.

---

## 3. Hard-retire — only when genuinely needed

Reserve this for a case where the value must actually disappear from the database (e.g. a
compliance/legal requirement, or a genuine schema cleanup where the zombie value itself is
unacceptable to leave behind) — not for ordinary vocabulary pruning, which §2 handles without any
DDL at all.

Procedure, **per enum type, per city**:

1. **Hand-author the migration. Never use the generated one.** Do not run
   `payload migrate:create` and apply what it proposes — per §1, its proposal is the destructive
   drop-and-recreate of the whole type. Write the migration by hand, in the same style as the
   existing hand-authored migrations in this codebase (e.g.
   `engine/packages/cms/src/migrations/20260910_060000_classification_reviews_no_clobber_trigger.ts`,
   which hand-writes a trigger Payload's generator has no notion of at all — the same principle:
   when the generator cannot express the change safely, write the SQL yourself).
2. Inside that hand-authored migration, in order:
   - `RENAME` the old enum type out of the way.
   - `CREATE` the new enum type with the retired value actually removed.
   - **`UPDATE` every column of the old type, in every table that has one, to a valid new-type
     value FIRST** — before the cast in the next step. This must happen in the *same* migration
     as the cast, not a prior one, and not left to an application-level backfill script: the
     whole point of ordering it this way is described next.
   - `ALTER COLUMN ... USING col::text::<new_type>` to cast each column from the old type to the
     new one.
   - `DROP` the old type.
3. **The data UPDATE must precede the cast, in the same migration, so the cast fails loudly if
   any row still holds the retired value.** `col::text::new_type` raises a Postgres error
   ("invalid input value for enum") for any row whose text does not match a label in the new
   type. That failure is the safety net: if step 2's UPDATE missed a row (a table `check-term-refs`
   didn't know to check, a race with a concurrent writer, a bad WHERE clause), the migration
   aborts instead of silently truncating or nulling data. Never re-order this so the cast runs
   before the guarantee that every row is already clean — that would turn a loud, safe failure
   into silent data loss.
4. This is real DDL against a live schema, per city, per type — treat it with the same weight as
   any other Payload/drizzle enum migration (F89's standing warning applies to every future one),
   and satisfy every gate in §4 before and after.

---

## 4. Gates — before and after any retirement (soft or hard)

- **`now-db check-term-refs` before and after** (F92). This is the referential-integrity
  detector for a shared vocabulary that Postgres cannot enforce with a real FK across databases
  (`now_platform.engine.terms` vs. each city DB's tables). Run it before touching anything, to
  know the current live-reference footprint of the term being retired, and again after, to
  confirm nothing was left dangling by the retirement itself.
- **Backups first.** Standard practice elsewhere in this project for any migration that touches
  real classified data (see the `f104-f113`/F125 precedent: `pg_dump --data-only
  --column-inserts` of the affected tables before running, with a documented restore path).
  Apply the same discipline here — back up every city DB's tables the term touches before either
  §2 or §3 begins.
- **Never run while a re-classification or LLM batch is in flight.** Both write `entity_terms`
  and `classification_reviews` continuously and key off the current vocabulary while running; a
  retirement mid-run risks the run seeing a term disappear (or a `retired_at` flip) partway
  through and producing inconsistent output for articles processed before vs. after the change.
  Confirm no such job is running before starting, the same way F124/T4's own constraints required
  proving no write landed on `now_jakarta`/`now_bali` while two concurrent agents (decay trust
  gate, LLM apply-step writer) were active against those same databases.
- **CMS restart required.** `cms/src/lib/vocabulary.ts` loads `engine.terms` once at process
  boot (F90) and freezes the resulting options array for the process's lifetime. Any change to a
  term's `attrs.retired_at`, label, or presence is invisible to a running `cms-<city>` process
  until it restarts — the same restart requirement F90 already established for E2.1's writes.

---

## 5. The prompt-fork prohibition

Changing a term's **description** or the **term set** itself while an LLM batch is mid-run forks
the labels the batch produces into two incompatible vocabularies — some articles labelled under
the old wording/set, later ones under the new. This is exactly the caution F124/T4 carried
forward from `now_eval.calibration.llm_client.FORMAT_DESCRIPTIONS`: that constant *is* the
vocabulary as the LLM sees it, and it scored 142/142 against Hansel's own adjudication under its
current wording. The same rule applies to retirement: do not soft- or hard-retire a term (which
changes the term set an LLM-facing vocabulary constant enumerates) while a batch using that
vocabulary is running. Finish or pause the batch first.

---

## 6. Seed files do not update existing rows — plan an explicit UPDATE path

`now_db.provisioning`'s `_UPSERT_TERM` seed upsert is written to converge label/parent/attrs on
re-seed (it is not a pure `ON CONFLICT DO NOTHING`) — but several *other* seed tables in this
package (`engine.type_relations` via `_INSERT_TYPE_RELATION`, for one) use
`ON CONFLICT DO NOTHING` **deliberately**, specifically so a site's local edits are never
clobbered by a re-run of the seed. F122 hit this directly: fixing `type_relations.json`'s
asymmetric `complements` lists in the seed file alone did **nothing** for cities that already had
rows — the seed's own `DO NOTHING` guarantee meant existing rows had to be `UPDATE`d by hand
against all three databases (`now_jakarta`, `now_bali`, `now_test`) and verified byte-identical to
the seed afterward.

The lesson for retirement: **do not assume editing a seed JSON file propagates anywhere.**
Whatever seed table backs the field you are changing as part of a retirement (setting
`attrs.retired_at`, relabelling an option, adjusting a relation), check whether that table's
upsert is fill-only (`DO NOTHING`) or converging (`_UPSERT_TERM`'s style) before relying on
`now-db migrate --all` to carry the change to already-provisioned databases. If it is fill-only,
write and run an explicit `UPDATE`, and verify the live rows afterward — the same "verify against
live data, not the schema" discipline F88 exists to remind everyone of (a column that exists but
is never read/written, or a seed change that is never applied to existing rows, both look fine
until you actually query the database).

---

## References

- F89 — the landmine this whole playbook exists to defuse (PROGRESS.md).
- F90 — CMS-boot vocabulary caching and the restart requirement (PROGRESS.md;
  `engine/packages/cms/src/lib/vocabulary.ts`).
- F92 / `now-db check-term-refs` — the referential-integrity detector
  (`engine/packages/db/src/now_db/term_refs.py`, `now_db/cli.py`).
- F88 — `engine.terms.attrs` was write-inert for a long time; the schema check passed the whole
  time it was broken. `retired_at` depends on this fix (PROGRESS.md; `now_db/provisioning.py`).
- F122 — seed files with `ON CONFLICT DO NOTHING` do not update existing rows; a real case where
  this was missed (PROGRESS.md; `engine/packages/taxonomy/seed/type_relations.json`).
- F124 — the investigation that raised the retirement question for `format` in the first place,
  and the prompt-fork prohibition's origin (PROGRESS.md;
  `engine/packages/eval/src/now_eval/calibration/llm_client.py`).
- Hand-authored migration precedent: `20260910_060000_classification_reviews_no_clobber_trigger.ts`
  (`engine/packages/cms/src/migrations/`) — writes SQL Payload's generator has no notion of, by
  hand, rather than trusting `migrate:create`.
