-- Apply `20260918_090000_articles_slug` on a host that cannot run the migration.
--
--   docker exec now-postgres psql -U now -d <city> -v ON_ERROR_STOP=1 \
--     -f /tmp/articles-slug.sql
--
-- The SQL twin of `src/migrations/20260918_090000_articles_slug.ts`, and it
-- exists for the reason docs/DEPLOY.md gives: `npx payload migrate` does NOT
-- work against the deployed image. The runner stage is a Next.js standalone
-- build — it carries `src/migrations/` but no `tsconfig.json` and no payload
-- module, so `npx` fetches a fresh Payload that dies in `getTSConfigPaths`.
-- The migration files ship; the CLI that applies them does not. Same
-- arrangement, same reason, as `backfill-article-versions.sql`.
--
-- ORDER MATTERS, AND IN ONE DIRECTION ONLY.
-- Run this BEFORE rolling the image that needs it. The column is additive and
-- the currently deployed build does not know it exists, so applying it early
-- is invisible to readers. The reverse order is an outage: the new code reads
-- `articles.slug`, and against a database without that column every article
-- page returns 500 while `/healthz` stays green.
--
-- WHY A SECOND IMPLEMENTATION IS SAFE HERE.
-- The statements below are copied verbatim from the migration's `up()`, which
-- is itself plain SQL in a `sql\`...\`` template rather than a query builder —
-- so this is a transcription, not a reimplementation. The only additions are
-- the transaction and the `payload_migrations` row, both of which the Payload
-- runner would otherwise do.
--
-- THE BACKFILL IS EXACT ON THIS ARCHIVE, AND THAT WAS MEASURED FIRST.
-- Across both cities: zero NULL `legacy_permalink`, zero empty, zero that are
-- not `/{slug}/` shaped, and the derived slug set fully distinct — 4,772 and
-- 4,429. `btrim(legacy_permalink, '/')` is therefore a total, collision-free
-- function here. That is a property of this data, not a guarantee about
-- permalinks, which is why the unique index is built AFTER the backfill: on a
-- city whose data does collide this fails loudly inside the transaction
-- instead of seating a duplicate that resolves someone else's article.

BEGIN;

ALTER TABLE "articles" ADD COLUMN "slug" varchar;
ALTER TABLE "_articles_v" ADD COLUMN "version_slug" varchar;

UPDATE "articles"
   SET "slug" = btrim("legacy_permalink", '/')
 WHERE "legacy_permalink" IS NOT NULL
   AND btrim("legacy_permalink", '/') <> ''
   AND "slug" IS NULL;

UPDATE "_articles_v"
   SET "version_slug" = btrim("version_legacy_permalink", '/')
 WHERE "version_legacy_permalink" IS NOT NULL
   AND btrim("version_legacy_permalink", '/') <> ''
   AND "version_slug" IS NULL;

-- Unique on the parent; NOT unique on the versions table, where up to 50
-- versions of one document legitimately carry the same slug (`maxPerDoc`).
CREATE UNIQUE INDEX "articles_slug_idx" ON "articles" USING btree ("slug");
CREATE INDEX "_articles_v_version_version_slug_idx" ON "_articles_v" USING btree ("version_slug");

-- Recorded as applied, so the Payload runner does not try it again the day
-- the image can migrate itself.
INSERT INTO payload_migrations (name, batch)
VALUES ('20260918_090000_articles_slug', (SELECT COALESCE(MAX(batch), 0) + 1 FROM payload_migrations));

COMMIT;

-- Verify, per city. Expect: articles = with_slug = distinct_slug, mismatch 0.
--
--   SELECT count(*) AS articles,
--          count(slug) AS with_slug,
--          count(DISTINCT slug) AS distinct_slug,
--          count(*) FILTER (
--            WHERE slug IS DISTINCT FROM btrim(legacy_permalink, '/')
--          ) AS mismatch
--     FROM public.articles;
