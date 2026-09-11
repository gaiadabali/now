import type { MigrateDownArgs, MigrateUpArgs } from '@payloadcms/db-postgres'
import { sql } from '@payloadcms/db-postgres'

/**
 * F49 + F51 (PROGRESS.md), one migration because they touch the same table
 * and both are trivial once `unknown` exists as an enum label (previous
 * migration, `20260909_150000_add_unknown_type_enum_value.ts` -- see that
 * file for why the enum ADD VALUE could not share a transaction with this
 * UPDATE).
 *
 * F49 -- migrate the 177 loader-sentinel places off `type='editorial'`
 * onto the new `unknown` type. Scoped to the *exact* sentinel triple
 * (`type='editorial' AND subtype='city-guide' AND status='pending_review'`)
 * from ARCHITECTURE.md §4/PROGRESS.md F27, not a bare `type='editorial'`,
 * so a genuine editorial article-adjacent place row (if one is ever added
 * before E2.1 finishes) is never swept up by accident. `status` is left
 * untouched per the brief ("keeping status='pending_review'") -- this
 * migration only changes what the row's type asserts, not its lifecycle
 * state. `subtype` is also left untouched (still `city-guide`): `subtype`
 * has no `unknown` child term (deliberately -- see
 * `taxonomy/seed/terms/type.json`), and nothing reads `places.subtype`
 * against `places.type` for consistency today, so there is no correctness
 * reason to invent a value here; E2.3 assigns a real type+subtype pair
 * together when it reclassifies these rows.
 *
 * Only the live `places` table is updated, not `_places_v` (Payload's
 * version-history table for this collection, `versions: { maxPerDoc: 20 }`,
 * no drafts). Version rows are the audit trail of what was true when they
 * were saved; the live document in `places` is what every reader (engine
 * queries, the exclusion filter, editors' current-state view) actually
 * sees, and Payload never falls back to `_places_v` to serve a "current"
 * document for a non-draft collection. Rewriting history rows to make it
 * look like a decision made months ago already accounted for a taxonomy
 * term added today would be the actual data-integrity problem.
 *
 * F51 -- `public.places` had no index supporting `(status, type)`, the
 * pair ARCHITECTURE.md §8.G's hard-filter ordering ("site → status → type
 * → area, cheap, selective, indexed → push into SQL") pushes into every
 * `now_filters` query (`hard.py`'s `WHERE status = 'active' AND
 * type::text != ALL(...)`). Geo already has `ix_places_geo` (GiST, from
 * the hand-authored places-geography migration); this is the equivalent
 * for the other half of that WHERE clause. Plain composite btree, column
 * order `(status, type)` to match the finding and the filter's own
 * left-to-right predicate order; not partial, since both the fully-active
 * competitor-exclusion query and any future "pending_review" moderation
 * queue query benefit from the same index.
 */
export async function up({ db }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
    UPDATE "places"
       SET "type" = 'unknown'
     WHERE "type" = 'editorial'
       AND "subtype" = 'city-guide'
       AND "status" = 'pending_review';

    CREATE INDEX IF NOT EXISTS "ix_places_status_type" ON "places" ("status", "type");
  `)
}

export async function down({ db }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
    DROP INDEX IF EXISTS "ix_places_status_type";

    UPDATE "places"
       SET "type" = 'editorial'
     WHERE "type" = 'unknown'
       AND "subtype" = 'city-guide'
       AND "status" = 'pending_review';
  `)
}
