import { MigrateUpArgs, MigrateDownArgs, sql } from '@payloadcms/db-postgres'

/**
 * S1.1 — `articles.slug`, the field that makes the CMS able to publish.
 *
 * **What was broken.** `public.articles` had no slug. An article's public
 * address was `legacy_permalink`, matched exactly by `getBySlug()` in the
 * reader app — and that field's own description reads *"DO NOT EDIT — every
 * redirect from the old site is matched on this exact string"*, which is
 * correct. So a writer who created a new article produced a row with no
 * reachable URL, and `toArticle()` mapped it to `slug: ''`, which made every
 * card linking to it point at the homepage. Places and Authors both have a
 * slug; Articles, the collection that needed one most, did not.
 *
 * **The backfill is exact, not best-effort.** Measured on both cities before
 * writing this: 4,772 Jakarta and 4,429 Bali rows, **zero** NULL or empty
 * permalinks, **zero** that are not `/{slug}/` shaped, and the derived slug
 * set is fully distinct in each city — 4,772 and 4,429 distinct values. So
 * `btrim(legacy_permalink, '/')` is a total, collision-free function here and
 * needs no disambiguation pass. That is a property of this data, not a
 * guarantee about permalinks in general, which is why the unique index is
 * created *after* the backfill: if a future city's data does collide, the
 * index build fails the migration loudly instead of letting a duplicate sit
 * in the table until someone's article silently resolves to another's.
 *
 * **Nullable on purpose.** Postgres allows many NULLs under a unique index,
 * so a draft saved before its slug is derived does not collide with every
 * other such draft. The collection's own `beforeValidate` hook fills it from
 * the title, so nothing reaches `published` without one.
 *
 * **The version table gets the column too.** `_articles_v` mirrors every
 * article field as `version_*`; a field added to the collection and not to
 * the version table makes autosave write a column that does not exist. Its
 * index is deliberately NOT unique — there are up to 50 versions per doc
 * (`maxPerDoc`), all of which legitimately carry the same slug.
 *
 * Per the standing rule from F79/F89: this was checked against what
 * `payload migrate:create` proposes and carries only the additive statements.
 * There is no enum in this change, so the stale-snapshot type-recreation
 * landmine those findings documented does not apply here.
 */
export async function up({ db }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
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

  CREATE UNIQUE INDEX "articles_slug_idx" ON "articles" USING btree ("slug");
  CREATE INDEX "_articles_v_version_version_slug_idx" ON "_articles_v" USING btree ("version_slug");`)
}

export async function down({ db }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
  DROP INDEX "articles_slug_idx";
  DROP INDEX "_articles_v_version_version_slug_idx";
  ALTER TABLE "articles" DROP COLUMN "slug";
  ALTER TABLE "_articles_v" DROP COLUMN "version_slug";`)
}
