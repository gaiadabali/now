import type { MigrateDownArgs, MigrateUpArgs } from '@payloadcms/db-postgres'
import { sql } from '@payloadcms/db-postgres'

/**
 * ITINERARY-AND-READER-PRODUCTS-PLAN.md §9.2 — adds `junk` to
 * `enum_places_status`. A junk row is a fragment the extractor produced
 * ("at Sunset Beach", a possessive, an award/franchise title, a single
 * dictionary word) — never a real venue, never rendered, never a candidate
 * anywhere — but its `place_mentions` are kept as evidence of what the
 * extractor did (§9.2: "a junk row becomes... no — junk is a fourth outcome
 * and deserves its own value"). Distinct from `closed`: a closed place was
 * real and is now gone; a junk row was never a place.
 *
 * **Split into its own migration, exactly like
 * `20260909_150000_add_unknown_type_enum_value.ts` did for `unknown`, for
 * the same hard Postgres constraint**: `ALTER TYPE ... ADD VALUE` may run
 * inside a transaction (PG12+), but the new label cannot be *used* — in a
 * column default, a `WHERE`/`SET` literal, even an implicit cast — inside
 * that same transaction (error 55P04, "unsafe use of new value of enum
 * type"). Payload wraps every migration file's `up()` in exactly one
 * transaction, so a single migration that both added `junk` and then wrote
 * it into a row would fail. This migration only adds the label; nothing
 * here (or in the companion fields migration that follows it) sets any
 * row's `status` to `junk` — that write happens later, in the triage
 * pipeline (P1.1, `now-places triage`), by which point this label has long
 * since been committed in its own prior migration/transaction.
 *
 * Both places' `status` enums get it, matching the `unknown` precedent's
 * own reasoning for touching every enum a shared vocabulary backs — except
 * `status` is NOT one of the four shared-taxonomy enums `unknown` touched
 * (`type`, on `places` and `articles`, both live and version tables); it is
 * `places`-only, so only the two `places`-side status enums (live +
 * version table) are touched here. `articles.status`/`events.status` are a
 * different, editorial-workflow enum (`draft`/`published`) and have no
 * `junk` concept.
 *
 * `IF NOT EXISTS` makes `up()` safe to re-run against a database where a
 * previous partial run already added the value.
 */
export async function up({ db }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
    ALTER TYPE "public"."enum_places_status" ADD VALUE IF NOT EXISTS 'junk';
    ALTER TYPE "public"."enum__places_v_version_status" ADD VALUE IF NOT EXISTS 'junk';
  `)
}

/**
 * Same recreate-the-type dance `20260909_150000_...`'s `down()` documents:
 * Postgres has never supported `DROP VALUE` for an enum label. This will
 * fail loudly — by design — if any row still has `status = 'junk'` at the
 * time it runs; an operator downgrading past this migration has to resolve
 * those rows (re-triage or hard-delete) first, which is a data decision
 * this script correctly refuses to make silently.
 */
export async function down({ db }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
    ALTER TYPE "public"."enum_places_status" RENAME TO "enum_places_status_old";
    CREATE TYPE "public"."enum_places_status" AS ENUM('active', 'closed', 'pending_review');
    ALTER TABLE "places" ALTER COLUMN "status" TYPE "public"."enum_places_status" USING "status"::text::"public"."enum_places_status";
    DROP TYPE "public"."enum_places_status_old";

    ALTER TYPE "public"."enum__places_v_version_status" RENAME TO "enum__places_v_version_status_old";
    CREATE TYPE "public"."enum__places_v_version_status" AS ENUM('active', 'closed', 'pending_review');
    ALTER TABLE "_places_v" ALTER COLUMN "version_status" TYPE "public"."enum__places_v_version_status" USING "version_status"::text::"public"."enum__places_v_version_status";
    DROP TYPE "public"."enum__places_v_version_status_old";
  `)
}
