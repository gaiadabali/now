-- Apply `20260924_111729_articles_created_by` on a host that cannot run the
-- migration.
--
--   docker cp articles-created-by.sql now-postgres:/tmp/
--   docker exec now-postgres psql -U now -d <city> -v ON_ERROR_STOP=1 \
--     -f /tmp/articles-created-by.sql
--
-- The SQL twin of `src/migrations/20260924_111729_articles_created_by.ts`,
-- for the exact reason `articles-slug.sql` exists: `npx payload migrate`
-- does not work against the deployed image (the runner stage is a Next.js
-- standalone build with no `tsconfig.json` and no `payload` module — see
-- docs/DEPLOY.md and that file's own header).
--
-- ORDER MATTERS, AND IN ONE DIRECTION ONLY.
-- Run this BEFORE rolling the image that needs it — same trap as S1.1's
-- slug migration. The column is additive and nullable, so the currently
-- deployed build (which selects it not at all) is unaffected by it existing
-- early. The reverse order is an outage: Payload's Local API selects every
-- declared column on every read, so the moment the new image runs against a
-- database WITHOUT `created_by_id`, every article query 500s while
-- `/healthz` stays green — the identical failure shape DEPLOY.md already
-- warns about for the slug column.
--
-- WHY A SECOND IMPLEMENTATION IS SAFE HERE.
-- Copied verbatim from the migration's `up()`, itself plain SQL rather than
-- a query builder — a transcription, not a reimplementation. The only
-- additions are the transaction and the `payload_migrations` row, which the
-- Payload runner would otherwise write itself.
--
-- NO BACKFILL. Existing rows keep `created_by_id IS NULL` — nothing recorded
-- who created any of them before today, and there is no honest way to guess
-- it (`author` is the public byline, not a login). The desk home says so in
-- plain words rather than pretending otherwise.

BEGIN;

ALTER TABLE "articles" ADD COLUMN "created_by_id" integer;
ALTER TABLE "_articles_v" ADD COLUMN "version_created_by_id" integer;

ALTER TABLE "articles" ADD CONSTRAINT "articles_created_by_id_users_id_fk"
  FOREIGN KEY ("created_by_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;
ALTER TABLE "_articles_v" ADD CONSTRAINT "_articles_v_version_created_by_id_users_id_fk"
  FOREIGN KEY ("version_created_by_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;

CREATE INDEX "articles_created_by_idx" ON "articles" USING btree ("created_by_id");
CREATE INDEX "_articles_v_version_version_created_by_idx" ON "_articles_v" USING btree ("version_created_by_id");

-- Recorded as applied, so the Payload runner does not try it again the day
-- the image can migrate itself.
INSERT INTO payload_migrations (name, batch)
VALUES ('20260924_111729_articles_created_by', (SELECT COALESCE(MAX(batch), 0) + 1 FROM payload_migrations));

COMMIT;

-- Verify, per city. Expect: created_by_count = 0 immediately after (no
-- backfill), rising only as new articles are created from here on.
--
--   SELECT count(*) AS articles,
--          count(created_by_id) AS created_by_count
--     FROM public.articles;
