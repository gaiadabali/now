import { MigrateUpArgs, MigrateDownArgs, sql } from '@payloadcms/db-postgres'

/**
 * F86 (PROGRESS.md) — make the review queue's no-clobber guarantee a
 * property of the DATA, not of one application-level query.
 *
 * Background: E2.8 shipped `classification-reviews` (migration
 * 20260910_020207) with the invariant "a human reviewer's decision must
 * never be silently overwritten by a later automated classification run."
 * `reviewQueueHooks.ts`'s `autoPopulateOnDecision` stamps `source='editor'`
 * on every transition INTO a decided state (`accepted`/`corrected`/
 * `unclassifiable`), and `scripts/verify-review-no-clobber.mjs` proved the
 * *intent* end-to-end — but the proof itself works because the simulated
 * `engine-worker` upsert happens to include a `WHERE source <> 'editor'`
 * clause. Nothing stops a DIFFERENT writer — a re-run of E2.1's classifier
 * calling Payload's REST/local API to re-propose the same (entity, facet)
 * and finding+updating the existing row, a backfill script, an ops
 * fix-up — from issuing a plain UPDATE that has no idea that clause needs
 * to exist. QA.6 demonstrated exactly this shape of gap against the
 * sibling `engine.entity_terms` table (naive `ON CONFLICT DO UPDATE` and a
 * plain `UPDATE` both clobbered an editor-sourced row); nothing in
 * `classification_reviews`'s own schema prevented the same class of bug
 * here, because CHECK (source IN (...)) only constrains which values are
 * legal, not which TRANSITIONS are legal once a human has decided.
 *
 * Fix: a BEFORE UPDATE trigger enforcing "once a row has been decided by a
 * human (review_state <> 'pending' AND source = 'editor'), any further
 * write must ALSO assert source = 'editor', or it is rejected outright."
 *
 * Why this predicate and not something narrower:
 *   - `review_state <> 'pending' AND source = 'editor'` is the exact
 *     condition `autoPopulateOnDecision` establishes on every legitimate
 *     decision — by construction, no other combination means "a human
 *     decided this" in the current app (only that hook ever sets
 *     `source='editor'`, always alongside a state transition).
 *   - Gating on `NEW.source` (not "no changes allowed at all") keeps every
 *     legitimate CMS path working: correcting an already-decided row
 *     (`accepted` -> `corrected`), or a plain re-save with `reviewState`
 *     unchanged, both submit the document's current `source` value, which
 *     is `'editor'` from the prior decision — see this migration's
 *     verification report for the actual exercised proof (Payload Local
 *     API round-trip, not just reasoning about the hook).
 *   - An automated writer's default `source` is `'ai'` (the column
 *     default) and E2.1/backfill code has no reason to spoof `'editor'` —
 *     mirrors the exact mechanism (`source`) QA.6's attack targeted on
 *     `engine.entity_terms`, so the same class of "naive upsert" or "plain
 *     UPDATE" is rejected here regardless of query shape (ON CONFLICT DO
 *     UPDATE also fires this trigger, since it is a row-level UPDATE event
 *     under the hood).
 *
 * This does NOT touch `engine.entity_terms` (a separate, Alembic-owned,
 * `engine`-schema table in `now_db`, out of scope for a Payload
 * migration — see ARCHITECTURE.md §1 "machines write engine, humans write
 * public"). `engine-worker`'s own upsert into `entity_terms` still needs
 * its own discipline (the `WHERE source <> 'editor'` predicate this
 * package's verify script already demonstrates) — that is tracked
 * separately, not weakened or duplicated by this change.
 *
 * Trigger + function are raw SQL, deliberately outside anything Payload's
 * collection-config-derived schema snapshot knows how to represent (no
 * collection field maps to "a trigger exists") — see this migration's
 * verification report for the actual `migrate:create` divergence check
 * this ticket required, run after this migration was applied.
 */
export async function up({ db, payload, req }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
    CREATE OR REPLACE FUNCTION public.classification_reviews_protect_human_decision()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $fn$
    BEGIN
      IF OLD.source = 'editor'
         AND OLD.review_state <> 'pending'
         AND NEW.source IS DISTINCT FROM 'editor'
      THEN
        RAISE EXCEPTION
          'classification_reviews id=%: this row was already decided by a human (review_state=%, source=editor) — an automated writer (source=%) may not overwrite that decision. Only a write that itself asserts source=''editor'' may modify a decided row. (F86)',
          OLD.id, OLD.review_state, NEW.source
          USING ERRCODE = 'restrict_violation';
      END IF;
      RETURN NEW;
    END;
    $fn$;

    COMMENT ON FUNCTION public.classification_reviews_protect_human_decision() IS
      'F86 no-clobber guard: once classification_reviews.review_state has left ''pending'' under source=''editor'', reject any UPDATE that does not itself assert source=''editor''. See migration 20260910_060000.';

    CREATE TRIGGER classification_reviews_no_clobber
      BEFORE UPDATE ON public.classification_reviews
      FOR EACH ROW
      EXECUTE FUNCTION public.classification_reviews_protect_human_decision();
  `)
}

export async function down({ db, payload, req }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
    DROP TRIGGER IF EXISTS classification_reviews_no_clobber ON public.classification_reviews;
    DROP FUNCTION IF EXISTS public.classification_reviews_protect_human_decision();
  `)
}
