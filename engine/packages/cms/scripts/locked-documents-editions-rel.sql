-- Apply `20260927_090100_locked_documents_editions_rel` on a host that
-- cannot run the migration (docs/DEPLOY.md).
--
--   docker exec now-postgres psql -U now -d <city> -v ON_ERROR_STOP=1 \
--     -f /tmp/locked-documents-editions-rel.sql
--
-- ORDER: after editions-collection.sql (it references "editions"). Until
-- this runs, every signed-in save in the admin fails on the lock check
-- (see the migration's header). Copied verbatim from the migration's up().

BEGIN;

ALTER TABLE "payload_locked_documents_rels" ADD COLUMN IF NOT EXISTS "editions_id" integer;
ALTER TABLE "payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_editions_fk"
  FOREIGN KEY ("editions_id") REFERENCES "public"."editions"("id") ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS "payload_locked_documents_rels_editions_id_idx"
  ON "payload_locked_documents_rels" USING btree ("editions_id");

INSERT INTO payload_migrations (name, batch)
VALUES ('20260927_090100_locked_documents_editions_rel', (SELECT COALESCE(MAX(batch), 0) + 1 FROM payload_migrations));

COMMIT;

-- Verify: expect one row.
--
--   SELECT column_name FROM information_schema.columns
--    WHERE table_name = 'payload_locked_documents_rels' AND column_name = 'editions_id';
