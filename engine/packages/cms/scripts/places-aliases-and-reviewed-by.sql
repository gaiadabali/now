-- Apply `20260927_090000_places_aliases_and_reviewed_by` on a host that
-- cannot run the migration (docs/DEPLOY.md).
--
--   docker exec now-postgres psql -U now -d <city> -v ON_ERROR_STOP=1 \
--     -f /tmp/places-aliases-and-reviewed-by.sql
--
-- ORDER MATTERS. Run AFTER places-provenance-and-curation-fields.sql (this
-- migration's FK references "places"/"users", both already present, but it
-- lands in the same append-only sequence as everything else in this file
-- set) and BEFORE rolling any image whose place desk (P1.6) reads/writes
-- `aliases` or `reviewed_by_id` — `src/collections/Places.ts` selects every
-- declared column, so the reverse order is a 500 on every place read.
--
-- Copied verbatim from the migration's `up()`. See that file's docstring
-- for why these two columns exist outside §9.2's own list (flagged
-- prominently in the PR per this repo's schema-change rule).

BEGIN;

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

INSERT INTO payload_migrations (name, batch)
VALUES ('20260927_090000_places_aliases_and_reviewed_by', (SELECT COALESCE(MAX(batch), 0) + 1 FROM payload_migrations));

COMMIT;

-- Verify, per city. Expect both new columns present and both new indexes.
--
--   SELECT column_name FROM information_schema.columns
--    WHERE table_name = 'places' AND column_name IN ('aliases', 'reviewed_by_id');
