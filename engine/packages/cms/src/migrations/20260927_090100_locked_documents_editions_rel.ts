import type { MigrateDownArgs, MigrateUpArgs } from '@payloadcms/db-postgres'
import { sql } from '@payloadcms/db-postgres'

/**
 * FLAGGED: a fix to Phase 0's `20260926_100000_editions_collection`, found
 * while building the place desk.
 *
 * Payload keeps one polymorphic join table for document locks,
 * `payload_locked_documents_rels`, with one `<collection>_id` column per
 * collection in the config. The Editions migration registered a new
 * collection but did not add `editions_id` to that table. Payload checks
 * locks on EVERY update made with a user, and that query names every
 * collection's column, so since Phase 0 any signed-in save in a city whose
 * database ran that migration fails with
 * `column "..."."editions_id" does not exist` — the place desk, the
 * classification desk and Payload's own edit screens alike. (Writes without
 * a user, like the CLIs and verify scripts, skip the lock check, which is
 * why Phase 0's own checks passed.)
 *
 * The column, foreign key and index follow the exact naming Payload
 * generated for the other nine collections in this table. Additive only.
 * SQL twin: scripts/locked-documents-editions-rel.sql.
 */
export async function up({ db }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
    ALTER TABLE "payload_locked_documents_rels" ADD COLUMN IF NOT EXISTS "editions_id" integer;
    ALTER TABLE "payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_editions_fk"
      FOREIGN KEY ("editions_id") REFERENCES "public"."editions"("id") ON DELETE CASCADE;
    CREATE INDEX IF NOT EXISTS "payload_locked_documents_rels_editions_id_idx"
      ON "payload_locked_documents_rels" USING btree ("editions_id");
  `)
}

export async function down({ db }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
    DROP INDEX IF EXISTS "payload_locked_documents_rels_editions_id_idx";
    ALTER TABLE "payload_locked_documents_rels" DROP CONSTRAINT IF EXISTS "payload_locked_documents_rels_editions_fk";
    ALTER TABLE "payload_locked_documents_rels" DROP COLUMN IF EXISTS "editions_id";
  `)
}
