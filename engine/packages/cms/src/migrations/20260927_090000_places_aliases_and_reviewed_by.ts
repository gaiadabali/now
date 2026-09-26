import type { MigrateDownArgs, MigrateUpArgs } from '@payloadcms/db-postgres'
import { sql } from '@payloadcms/db-postgres'

/**
 * FLAGGED PROMINENTLY, PER THIS TICKET'S RULE ("Schema: Phase 0 already added
 * the place fields. If you truly need another column, add a Payload
 * migration WITH a SQL twin and the matching collection config, and flag it
 * prominently in the PR"): §9.2/§9.3 do not name these two columns, and this
 * ticket's own P1.2/P1.6 briefs need them anyway —
 *
 *   - `aliases` (json, nullable) — P1.2's "done when": "a merge round-trips
 *     (mentions moved, survivor keeps both names as aliases)". `merged_into`
 *     points one way (loser → survivor) and cannot carry the loser's name
 *     once that row is hidden. A nullable jsonb column on the SURVIVOR,
 *     following the `externalTypes` precedent in the previous migration,
 *     rather than a `hasMany` field (which would generate a join table this
 *     file cannot hand-verify). Each entry is also the merge's AUDIT RECORD:
 *     `{name, placeId, mergedAt, by, score, mentionIds, repointedPlaceIds,
 *     inheritedAliases}` — enough for `now-places unmerge` to reverse the
 *     merge exactly. Written only by merges (`now-places dedupe/merge` and
 *     the place desk's merge action), in the same transaction that moves
 *     `place_mentions` and sets `merged_into_id`; read-only in the admin.
 *
 *   - `reviewedBy` (relationship → users, nullable) — §9.2's own text says
 *     the place desk (P1.6) "is a custom admin view over `places` itself
 *     with per-row actions... and every decision is a Payload `update` (a
 *     version, `reviewedBy`, hooks) rather than raw SQL" — `reviewedBy` is
 *     named explicitly in that very sentence but was not actually added to
 *     the §9.2 column list two paragraphs above it. Without it, "a version
 *     with the actor" is only half true: Payload's own version row
 *     (`_places_v`) has no user-identifying column of its own (verified
 *     live against `_places_v`'s generated schema — it carries the parent
 *     id, the versioned field snapshot and timestamps, nothing else), so
 *     "who approved this place" would otherwise be unrecoverable the moment
 *     a second version supersedes the first. Mirrors `mergedInto`'s own
 *     shape exactly: a Payload `relationship` field, `ON DELETE SET NULL`
 *     (an editor account being removed must not block or cascade-delete the
 *     place row it once reviewed), same FK/index naming Payload already
 *     generated for `articles.author_id → authors.id` in the initial
 *     schema.
 *
 * Both fields ship in the SAME commit as their `src/collections/Places.ts`
 * additions, per that file's own standing rule (Payload selects every
 * declared column).
 */
export async function up({ db }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
    ALTER TABLE "places"
      ADD COLUMN "aliases" jsonb,
      ADD COLUMN "reviewed_by_id" integer;

    ALTER TABLE "_places_v"
      ADD COLUMN "version_aliases" jsonb,
      ADD COLUMN "version_reviewed_by_id" integer;

    ALTER TABLE "places" ADD CONSTRAINT "places_reviewed_by_id_users_id_fk"
      FOREIGN KEY ("reviewed_by_id") REFERENCES "users"("id") ON DELETE SET NULL;
    ALTER TABLE "_places_v" ADD CONSTRAINT "_places_v_version_reviewed_by_id_users_id_fk"
      FOREIGN KEY ("version_reviewed_by_id") REFERENCES "users"("id") ON DELETE SET NULL;

    CREATE INDEX "places_reviewed_by_idx" ON "places" USING btree ("reviewed_by_id");
    CREATE INDEX "_places_v_version_version_reviewed_by_idx" ON "_places_v" USING btree ("version_reviewed_by_id");
  `)
}

export async function down({ db }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
    DROP INDEX IF EXISTS "_places_v_version_version_reviewed_by_idx";
    DROP INDEX IF EXISTS "places_reviewed_by_idx";

    ALTER TABLE "_places_v" DROP CONSTRAINT IF EXISTS "_places_v_version_reviewed_by_id_users_id_fk";
    ALTER TABLE "places" DROP CONSTRAINT IF EXISTS "places_reviewed_by_id_users_id_fk";

    ALTER TABLE "_places_v"
      DROP COLUMN IF EXISTS "version_reviewed_by_id",
      DROP COLUMN IF EXISTS "version_aliases";

    ALTER TABLE "places"
      DROP COLUMN IF EXISTS "reviewed_by_id",
      DROP COLUMN IF EXISTS "aliases";
  `)
}
