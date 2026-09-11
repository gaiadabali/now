import { MigrateUpArgs, MigrateDownArgs, sql } from '@payloadcms/db-postgres'

// F99 final report — adds `places.legacy_wp_id`, mirroring `events.legacy_wp_id` /
// `articles.legacy_wp_id`, so the 177 legacy-WP-imported venues (and any future direct
// WP venue import) have the same idempotent join-key-back-to-source convention already
// used everywhere else. NULL for the ~12,400 E2.3-extracted places, which have no single
// source WP entity.
//
// `payload migrate:create` bundled this additive change together with a SPURIOUS
// `enum_places_area_term` / `enum__places_v_version_area_term` DROP+CREATE (dropping
// `rawamangun`, which F89 already retired from the vocabulary) — the exact stale-snapshot
// type-recreation landmine F79/F89 documented and warned every future enum-adjacent
// migration to expect. Per that standing rule: generated, confirmed, and stripped rather
// than applied. Only the genuine additive statements survive below.
export async function up({ db, payload, req }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
   ALTER TABLE "places" ADD COLUMN "legacy_wp_id" numeric;
  ALTER TABLE "_places_v" ADD COLUMN "version_legacy_wp_id" numeric;
  CREATE UNIQUE INDEX "places_legacy_wp_id_idx" ON "places" USING btree ("legacy_wp_id");
  CREATE INDEX "_places_v_version_version_legacy_wp_id_idx" ON "_places_v" USING btree ("version_legacy_wp_id");`)
}

export async function down({ db, payload, req }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
   DROP INDEX "places_legacy_wp_id_idx";
  DROP INDEX "_places_v_version_version_legacy_wp_id_idx";
  ALTER TABLE "places" DROP COLUMN "legacy_wp_id";
  ALTER TABLE "_places_v" DROP COLUMN "version_legacy_wp_id";`)
}
