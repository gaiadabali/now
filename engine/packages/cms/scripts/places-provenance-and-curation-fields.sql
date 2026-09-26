-- Apply `20260926_090100_places_provenance_and_curation_fields` on a host
-- that cannot run the migration (docs/DEPLOY.md).
--
--   docker exec now-postgres psql -U now -d <city> -v ON_ERROR_STOP=1 \
--     -f /tmp/places-provenance-and-curation-fields.sql
--
-- ORDER MATTERS, AND IN ONE DIRECTION ONLY.
-- Run AFTER places-junk-status-enum-value.sql (unrelated enum, but keeps the
-- same landing order as the migration set) and BEFORE rolling any image
-- whose Places admin screen or the place desk (P1.6) reads these columns —
-- `src/collections/Places.ts` selects every declared column, so the reverse
-- order is a 500 on every place read while `/healthz` stays green, the same
-- failure mode `articles-slug.sql` warns about.
--
-- THE BACKFILL IS EXACT ON THIS ARCHIVE, MEASURED FIRST (see the migration's
-- own docstring for the query used to check it): every row today is
-- `status = 'pending_review'`, `legacy_wp_id IS NOT NULL` on exactly 177
-- Bali rows and 0 Jakarta rows, so `legacy_wp_id IS NOT NULL -> 'legacy_venue'`
-- else `'extracted'` is total over every row in both cities.
--
-- Copied verbatim from the migration's `up()`.

BEGIN;

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
  ADD COLUMN "region_ok" boolean DEFAULT false NOT NULL,
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
CREATE INDEX "places_source_idx" ON "places" USING btree ("source");
CREATE INDEX "places_quality_score_idx" ON "places" USING btree ("quality_score");

INSERT INTO payload_migrations (name, batch)
VALUES ('20260926_090100_places_provenance_and_curation_fields', (SELECT COALESCE(MAX(batch), 0) + 1 FROM payload_migrations));

COMMIT;

-- Verify, per city. Expect: total = with_source (100% backfilled), and the
-- mismatch count is 0 (every legacy_venue row really has a legacy_wp_id).
--
--   SELECT count(*) AS total,
--          count(source) AS with_source,
--          count(*) FILTER (WHERE source = 'legacy_venue' AND legacy_wp_id IS NULL) AS mismatch
--     FROM public.places;
