import type { MigrateDownArgs, MigrateUpArgs } from '@payloadcms/db-postgres'
import { sql } from '@payloadcms/db-postgres'

/**
 * F49 (PROGRESS.md) -- adds the `unknown` sentinel type to the Postgres
 * ENUMs Payload generated for the shared `type` facet (ARCHITECTURE.md §4).
 * See `src/collections/Places.ts` / `src/collections/Articles.ts` and
 * `engine/packages/taxonomy/seed/terms/type.json` for the taxonomy side of
 * this change -- that seed is what makes `now-db migrate --all` back-fill
 * `engine.type_relations` with `unknown` (`exclude_same=true`, zero
 * complements); this migration is the Payload/`public`-schema half F20
 * warned would be needed the moment a term was added.
 *
 * **Split into its own migration, hand-authored rather than generated, for
 * a real Postgres constraint, not a style choice**: `ALTER TYPE ... ADD
 * VALUE` may run inside a transaction (Postgres 12+), but the new value
 * cannot be *used* — referenced in a column default, a WHERE/SET literal,
 * even an implicit cast — inside that same transaction. Payload wraps every
 * migration file's `up()` in exactly one transaction
 * (`@payloadcms/drizzle`'s `runMigrationFile`), so a single migration that
 * both added 'unknown' and then `UPDATE`d rows to it would fail with
 * Postgres error 55P04 ("unsafe use of new value of enum type"). The
 * correct fix is two migrations, not a looser column type (`text` would
 * lose the enum's guard-rail against a typo'd type value reaching
 * `public.places`/`public.articles` — exactly the guarantee F20 documents
 * this ENUM exists for): this one only adds the label and does not use it;
 * `20260909_150100_places_unknown_type_and_status_type_index.ts` runs after
 * (a later migration file = a later, separate transaction, by
 * construction) and is the one that writes `type = 'unknown'` into rows.
 *
 * `IF NOT EXISTS` makes `up()` safe to re-run against a database where a
 * previous partial run already added the value (Postgres 9.6+ supports the
 * clause on `ADD VALUE`).
 *
 * Four enums share the same seeded `type` vocabulary (ARCHITECTURE.md §4,
 * `taxonomy/seed/terms/type.json`) because both `places.type`
 * (`vocabularySelectField(..., facetKey: 'type')`) and
 * `articles.primaryType` (same facetKey) build their Payload `select`
 * options from it, and Payload generates one Postgres ENUM per
 * (collection, field, +version-table variant). `unknown` is meaningful
 * today only for `places` (F49's loader sentinel) but the four enums are
 * definitionally the same vocabulary, so leaving `articles`' pair behind
 * would silently fork one shared facet into two different enum
 * definitions -- keeping all four in lockstep is the option that matches
 * "one taxonomy, seeded once" rather than a scope trim.
 */
export async function up({ db }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
    ALTER TYPE "public"."enum_places_type" ADD VALUE IF NOT EXISTS 'unknown';
    ALTER TYPE "public"."enum__places_v_version_type" ADD VALUE IF NOT EXISTS 'unknown';
    ALTER TYPE "public"."enum_articles_primary_type" ADD VALUE IF NOT EXISTS 'unknown';
    ALTER TYPE "public"."enum__articles_v_version_primary_type" ADD VALUE IF NOT EXISTS 'unknown';
  `)
}

/**
 * Postgres has never supported `DROP VALUE` for an enum label, so removing
 * one means recreating the type: rename the old type out of the way,
 * create a new type with the original name and value list, repoint every
 * column that used it (`USING <col>::text::<new type>`), then drop the old
 * type. This will fail loudly (by design) if any row still has
 * `type = 'unknown'` at the time this runs -- exactly what should happen,
 * since a value cast back to the narrower enum would either error or
 * silently need a decision this migration cannot make. Run
 * `20260909_150100_...`'s `down()` first (Payload's own `migrateDown`
 * already does this: migrations in a batch roll back in reverse name
 * order) so no row still references 'unknown' when this executes.
 */
export async function down({ db }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
    ALTER TYPE "public"."enum_places_type" RENAME TO "enum_places_type_old";
    CREATE TYPE "public"."enum_places_type" AS ENUM('do', 'drink', 'eat', 'editorial', 'event', 'shop', 'stay', 'wellness');
    ALTER TABLE "places" ALTER COLUMN "type" TYPE "public"."enum_places_type" USING "type"::text::"public"."enum_places_type";
    DROP TYPE "public"."enum_places_type_old";

    ALTER TYPE "public"."enum__places_v_version_type" RENAME TO "enum__places_v_version_type_old";
    CREATE TYPE "public"."enum__places_v_version_type" AS ENUM('do', 'drink', 'eat', 'editorial', 'event', 'shop', 'stay', 'wellness');
    ALTER TABLE "_places_v" ALTER COLUMN "version_type" TYPE "public"."enum__places_v_version_type" USING "version_type"::text::"public"."enum__places_v_version_type";
    DROP TYPE "public"."enum__places_v_version_type_old";

    ALTER TYPE "public"."enum_articles_primary_type" RENAME TO "enum_articles_primary_type_old";
    CREATE TYPE "public"."enum_articles_primary_type" AS ENUM('do', 'drink', 'eat', 'editorial', 'event', 'shop', 'stay', 'wellness');
    ALTER TABLE "articles" ALTER COLUMN "primary_type" TYPE "public"."enum_articles_primary_type" USING "primary_type"::text::"public"."enum_articles_primary_type";
    DROP TYPE "public"."enum_articles_primary_type_old";

    ALTER TYPE "public"."enum__articles_v_version_primary_type" RENAME TO "enum__articles_v_version_primary_type_old";
    CREATE TYPE "public"."enum__articles_v_version_primary_type" AS ENUM('do', 'drink', 'eat', 'editorial', 'event', 'shop', 'stay', 'wellness');
    ALTER TABLE "_articles_v" ALTER COLUMN "version_primary_type" TYPE "public"."enum__articles_v_version_primary_type" USING "version_primary_type"::text::"public"."enum__articles_v_version_primary_type";
    DROP TYPE "public"."enum__articles_v_version_primary_type_old";
  `)
}
