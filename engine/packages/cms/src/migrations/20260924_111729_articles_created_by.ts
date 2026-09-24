import { MigrateUpArgs, MigrateDownArgs, sql } from '@payloadcms/db-postgres'

/**
 * `articles.createdBy` — approved 2026-09-24 as a follow-up to the desk
 * home's "my drafts": there was no reliable link between a document and the
 * CMS login that started it (`author` is the public byline, `Authors.ts`'s
 * own header — "not to `users`"), so that count could only match on name,
 * best-effort, and said so on screen.
 *
 * **`payload migrate:create` proposed a great deal more than this column,
 * and none of the rest is trimmed by accident.** Per the standing rule from
 * F79/F89 (also invoked by `20260918_090000_articles_slug.ts`): the
 * generator diffs against the last committed Drizzle snapshot, and several
 * migrations in this directory are hand-written SQL with no matching
 * snapshot update (this one included, once written) — so the diff also
 * proposed re-adding `articles.slug` (already a real column since S1.1;
 * re-running that statement would fail with "column already exists") and a
 * batch of `users` drift (dropping `login_attempts`/`lock_until`/password
 * columns, the `users_sessions` table, and adding `'none'` to
 * `enum_users_role`) that is already true of the live database —
 * `Users.ts` has carried `disableLocalStrategy: true` and the `'none'` role
 * option since the admin consolidation, just never through a migration this
 * generator's snapshot recorded. None of that is this change; only the two
 * statements below are.
 *
 * **Nullable, and stays that way for existing rows.** There is no honest
 * backfill — nothing recorded who created any of the archive's rows before
 * today, and guessing (e.g. from `author`, which is a byline, not a login)
 * would manufacture a fact. `stampCreatedBy` (the collection hook) sets this
 * on every future create; the desk home says plainly, in the reader's words,
 * that a story from before today has nobody recorded here.
 *
 * **The version table gets the column too**, same reasoning as
 * `20260918_090000_articles_slug.ts`: `_articles_v` mirrors every article
 * field as `version_*`, and skipping it here would make autosave try to
 * write a column that does not exist.
 */
export async function up({ db }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
  ALTER TABLE "articles" ADD COLUMN "created_by_id" integer;
  ALTER TABLE "_articles_v" ADD COLUMN "version_created_by_id" integer;

  ALTER TABLE "articles" ADD CONSTRAINT "articles_created_by_id_users_id_fk"
    FOREIGN KEY ("created_by_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "_articles_v" ADD CONSTRAINT "_articles_v_version_created_by_id_users_id_fk"
    FOREIGN KEY ("version_created_by_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;

  CREATE INDEX "articles_created_by_idx" ON "articles" USING btree ("created_by_id");
  CREATE INDEX "_articles_v_version_version_created_by_idx" ON "_articles_v" USING btree ("version_created_by_id");`)
}

export async function down({ db }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
  ALTER TABLE "articles" DROP CONSTRAINT "articles_created_by_id_users_id_fk";
  ALTER TABLE "_articles_v" DROP CONSTRAINT "_articles_v_version_created_by_id_users_id_fk";
  DROP INDEX "articles_created_by_idx";
  DROP INDEX "_articles_v_version_version_created_by_idx";
  ALTER TABLE "articles" DROP COLUMN "created_by_id";
  ALTER TABLE "_articles_v" DROP COLUMN "version_created_by_id";`)
}
