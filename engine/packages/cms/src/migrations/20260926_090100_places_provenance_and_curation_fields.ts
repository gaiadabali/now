import type { MigrateDownArgs, MigrateUpArgs } from '@payloadcms/db-postgres'
import { sql } from '@payloadcms/db-postgres'

/**
 * ITINERARY-AND-READER-PRODUCTS-PLAN.md §9.2 — the provenance, geocoding
 * and curation columns the place desk (P1.6) and the resolver pipeline
 * (P1.3-P1.5) need. Ships together with `src/collections/Places.ts`'s field
 * additions in the same commit — Payload selects every declared column
 * (that file's own top comment, and README.md), so a config with these
 * fields and a database without these columns is a 500 on every place
 * read, and the reverse (columns with no config) is silent dead data no
 * screen can ever show or write.
 *
 * Runs after `20260926_090000_places_junk_status_enum_value.ts` — unrelated
 * to that migration's enum (this one adds four *new* enums, it does not
 * touch `enum_places_status`), but keeping "the `junk` value exists" as its
 * own committed transaction before anything else about §9.2 lands is the
 * same ordering discipline that migration's own docstring argues for.
 *
 * ## `source` is backfilled and made `NOT NULL` — measured on this archive
 * first, not assumed
 *
 * Same discipline as `20260918_090000_articles_slug.ts`: checked before
 * writing the backfill, not after. Every row in both cities is `status =
 * 'pending_review'` today (12,507 total, matching §9.1's own count exactly
 * — neither city has been through any curation yet), and `legacy_wp_id` is
 * NOT NULL on exactly 177 Bali rows and 0 Jakarta rows — every other row
 * came from E2.3 text extraction (`Places.ts`'s own `legacyWpId` field
 * description). So `legacy_wp_id IS NOT NULL -> 'legacy_venue'`, else
 * `'extracted'`, is a **total** function over every row that exists today
 * in every environment this has been checked against — verified with:
 *
 *     SELECT count(*), count(legacy_wp_id) FROM places;   -- both cities
 *
 * before writing the `UPDATE` below, the same way the slug migration
 * verified its own backfill was collision-free before relying on it. No
 * row is created with `source = 'editor'` or `'partner'` by this backfill
 * — nothing in this archive was editor- or partner-created before this
 * migration existed to name that provenance, by construction.
 *
 * `_places_v` (the version-history table) gets the identical backfill
 * against its own `version_legacy_wp_id` — same reasoning
 * `20260918_090000_articles_slug.ts` gave for backfilling `_articles_v`
 * alongside `articles`: a field added to the collection and not to the
 * version table makes autosave write a column that does not exist, and
 * `source` is `required: true` on the live field (`Places.ts`), which
 * Payload mirrors as `NOT NULL` on the version column too — exactly the
 * same shape `version_type`/`version_status` already have, both backing
 * `required: true` fields.
 *
 * ## Every other new column is nullable, by design, not oversight
 *
 * `merged_into`, `quality_score`, `business_status`, `external_types`,
 * `geo_source`, `geo_confidence`, `region_ok`, `hours_source`,
 * `hours_checked_at` are all populated by a pipeline stage (P1.2-P1.5)
 * that has not run yet on this archive — a `NOT NULL` on any of them
 * would either need a meaningless backfill value (a `geo_confidence` of
 * `0` is not "unknown", it is a false claim of certainty) or block this
 * migration on work that belongs to Phase 1, not Phase 0.
 *
 * `region_ok` was briefly the one deliberate exception (`NOT NULL DEFAULT
 * false`) on the reasoning that a computed boolean's absence should not
 * blur into a third, undocumented state — caught in review as
 * inconsistent with its own field instead: `Places.ts`'s `regionOk` is
 * not `required: true`, and Payload's mirrored version-table column,
 * `_places_v.version_region_ok`, was correctly generated nullable (a
 * required field's `NOT NULL` propagates to the version table too — see
 * `Editions.ts`'s docstring for where that was checked directly against a
 * live `_places_v`), so the live table's `NOT NULL` was the one column in
 * this migration that did not match what the collection config actually
 * declares — the exact "migration and config must land together, and
 * must agree" rule this file's own top comment states. Fixed to
 * nullable, `DEFAULT false` kept for the same reason every other
 * `DEFAULT` in this migration is kept alongside a dropped/absent
 * `NOT NULL`: existing and newly-inserted rows that omit the column still
 * get `false` from the column default (a `DEFAULT` fires whenever a
 * column is left out of an `INSERT`, regardless of nullability) — only an
 * explicit `NULL` write, which nothing in this migration performs, would
 * ever produce one. Nullable only widens what CAN be stored; it changes
 * nothing about what actually gets stored today.
 *
 * ## `merged_into` is a self-relation, `ON DELETE SET NULL`
 *
 * A place that survives a merge must not be silently deleted if the
 * duplicate pointing at it is later removed — `SET NULL` (not `CASCADE`,
 * not `RESTRICT`) matches every other relationship FK Payload has already
 * generated in this schema (`hero_media_id`, `author_id`, ...), all of
 * which use `ON DELETE SET NULL` because Payload relationship fields are
 * never the thing enforcing existence of their target.
 */
export async function up({ db }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
    CREATE TYPE "public"."enum_places_source" AS ENUM('extracted', 'legacy_venue', 'editor', 'partner');
    CREATE TYPE "public"."enum__places_v_version_source" AS ENUM('extracted', 'legacy_venue', 'editor', 'partner');
    CREATE TYPE "public"."enum_places_business_status" AS ENUM('operational', 'temporarily_closed', 'permanently_closed', 'unknown');
    CREATE TYPE "public"."enum__places_v_version_business_status" AS ENUM('operational', 'temporarily_closed', 'permanently_closed', 'unknown');
    CREATE TYPE "public"."enum_places_geo_source" AS ENUM('fsq', 'overture', 'osm', 'mappress', 'editor', 'partner');
    CREATE TYPE "public"."enum__places_v_version_geo_source" AS ENUM('fsq', 'overture', 'osm', 'mappress', 'editor', 'partner');
    CREATE TYPE "public"."enum_places_hours_source" AS ENUM('editor', 'partner');
    CREATE TYPE "public"."enum__places_v_version_hours_source" AS ENUM('editor', 'partner');

    ALTER TABLE "places"
      ADD COLUMN "source" "public"."enum_places_source",
      ADD COLUMN "merged_into_id" integer,
      ADD COLUMN "quality_score" numeric,
      ADD COLUMN "business_status" "public"."enum_places_business_status",
      ADD COLUMN "external_types" jsonb,
      ADD COLUMN "geo_source" "public"."enum_places_geo_source",
      ADD COLUMN "geo_confidence" numeric,
      ADD COLUMN "region_ok" boolean DEFAULT false,
      ADD COLUMN "hours_source" "public"."enum_places_hours_source",
      ADD COLUMN "hours_checked_at" timestamp(3) with time zone;

    ALTER TABLE "_places_v"
      ADD COLUMN "version_source" "public"."enum__places_v_version_source",
      ADD COLUMN "version_merged_into_id" integer,
      ADD COLUMN "version_quality_score" numeric,
      ADD COLUMN "version_business_status" "public"."enum__places_v_version_business_status",
      ADD COLUMN "version_external_types" jsonb,
      ADD COLUMN "version_geo_source" "public"."enum__places_v_version_geo_source",
      ADD COLUMN "version_geo_confidence" numeric,
      ADD COLUMN "version_region_ok" boolean DEFAULT false,
      ADD COLUMN "version_hours_source" "public"."enum__places_v_version_hours_source",
      ADD COLUMN "version_hours_checked_at" timestamp(3) with time zone;

    -- Backfill, verified exact on this archive (see docstring) before the
    -- NOT NULL below.
    UPDATE "places"
       SET "source" = CASE WHEN "legacy_wp_id" IS NOT NULL THEN 'legacy_venue' ELSE 'extracted' END::"public"."enum_places_source"
     WHERE "source" IS NULL;
    UPDATE "_places_v"
       SET "version_source" = CASE WHEN "version_legacy_wp_id" IS NOT NULL THEN 'legacy_venue' ELSE 'extracted' END::"public"."enum__places_v_version_source"
     WHERE "version_source" IS NULL;

    ALTER TABLE "places" ALTER COLUMN "source" SET NOT NULL;
    ALTER TABLE "_places_v" ALTER COLUMN "version_source" SET NOT NULL;

    ALTER TABLE "places" ADD CONSTRAINT "places_merged_into_id_places_id_fk"
      FOREIGN KEY ("merged_into_id") REFERENCES "places"("id") ON DELETE SET NULL;
    ALTER TABLE "_places_v" ADD CONSTRAINT "_places_v_version_merged_into_id_places_id_fk"
      FOREIGN KEY ("version_merged_into_id") REFERENCES "places"("id") ON DELETE SET NULL;

    CREATE INDEX "places_merged_into_idx" ON "places" USING btree ("merged_into_id");
    CREATE INDEX "_places_v_version_version_merged_into_idx" ON "_places_v" USING btree ("version_merged_into_id");

    -- The place desk's queue order (§9.1: rank, then work top-down) and the
    -- "0 junk rows active" / "no Google field stored" gates (§9.5) both
    -- filter on these columns from day one of Phase 1.
    CREATE INDEX "places_source_idx" ON "places" USING btree ("source");
    CREATE INDEX "places_quality_score_idx" ON "places" USING btree ("quality_score");
  `)
}

export async function down({ db }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
    DROP INDEX IF EXISTS "places_quality_score_idx";
    DROP INDEX IF EXISTS "places_source_idx";
    DROP INDEX IF EXISTS "_places_v_version_version_merged_into_idx";
    DROP INDEX IF EXISTS "places_merged_into_idx";

    ALTER TABLE "_places_v" DROP CONSTRAINT IF EXISTS "_places_v_version_merged_into_id_places_id_fk";
    ALTER TABLE "places" DROP CONSTRAINT IF EXISTS "places_merged_into_id_places_id_fk";

    ALTER TABLE "_places_v"
      DROP COLUMN IF EXISTS "version_source",
      DROP COLUMN IF EXISTS "version_merged_into_id",
      DROP COLUMN IF EXISTS "version_quality_score",
      DROP COLUMN IF EXISTS "version_business_status",
      DROP COLUMN IF EXISTS "version_external_types",
      DROP COLUMN IF EXISTS "version_geo_source",
      DROP COLUMN IF EXISTS "version_geo_confidence",
      DROP COLUMN IF EXISTS "version_region_ok",
      DROP COLUMN IF EXISTS "version_hours_source",
      DROP COLUMN IF EXISTS "version_hours_checked_at";

    ALTER TABLE "places"
      DROP COLUMN IF EXISTS "source",
      DROP COLUMN IF EXISTS "merged_into_id",
      DROP COLUMN IF EXISTS "quality_score",
      DROP COLUMN IF EXISTS "business_status",
      DROP COLUMN IF EXISTS "external_types",
      DROP COLUMN IF EXISTS "geo_source",
      DROP COLUMN IF EXISTS "geo_confidence",
      DROP COLUMN IF EXISTS "region_ok",
      DROP COLUMN IF EXISTS "hours_source",
      DROP COLUMN IF EXISTS "hours_checked_at";

    DROP TYPE IF EXISTS "public"."enum__places_v_version_hours_source";
    DROP TYPE IF EXISTS "public"."enum_places_hours_source";
    DROP TYPE IF EXISTS "public"."enum__places_v_version_geo_source";
    DROP TYPE IF EXISTS "public"."enum_places_geo_source";
    DROP TYPE IF EXISTS "public"."enum__places_v_version_business_status";
    DROP TYPE IF EXISTS "public"."enum_places_business_status";
    DROP TYPE IF EXISTS "public"."enum__places_v_version_source";
    DROP TYPE IF EXISTS "public"."enum_places_source";
  `)
}
