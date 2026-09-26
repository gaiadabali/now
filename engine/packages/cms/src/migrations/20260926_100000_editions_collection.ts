import type { MigrateDownArgs, MigrateUpArgs } from '@payloadcms/db-postgres'
import { sql } from '@payloadcms/db-postgres'

/**
 * `editions` — ITINERARY-AND-READER-PRODUCTS-PLAN.md §5.2. See
 * `src/collections/Editions.ts` for the collection config and the field-
 * level reasoning (in particular: nothing here is `NOT NULL` beyond
 * Payload's own housekeeping columns — every content field stays nullable
 * on purpose, so autosaving a fresh draft never hits a database-level
 * constraint a version-table mirror would otherwise impose).
 *
 * **Hand-authored against this Payload version's confirmed generation
 * shape, not machine-generated.** This worktree could not get
 * `payload migrate:create` running end-to-end (the CLI needs a live
 * `DATABASE_URI` and a built import map this isolated environment does not
 * have), so every naming/typing choice below was cross-checked against a
 * live, already-migrated city database instead: relationship/upload fields
 * → a plain `<field>_id integer` column with `ON DELETE SET NULL`
 * regardless of `required` (confirmed against `articles.hero_media_id`,
 * `events.place_id`, `place_mentions.article_id`/`place_id`); an `array`
 * field → a child table (`_order integer`, `_parent_id integer ON DELETE
 * CASCADE`, a Payload-generated `varchar` `id`, confirmed against
 * `places_hours`); `versions.drafts` → a `_status` enum column plus a
 * `_<collection>_v` version table whose columns are each `version_<field>`,
 * with a doubled underscore for `_status` specifically (`version__status`,
 * confirmed against `_articles_v`); a `textarea` field → `varchar`
 * (confirmed against `events.dek`). Before this ships, running
 * `payload migrate:create` in an environment with a working `DATABASE_URI`
 * against a database already at this migration and diffing the result
 * against this file is the strongest remaining check — recorded here so
 * that step is not skipped by mistake, not because there is a known error,
 * but because a naming mismatch here (unlike a wrong index elsewhere in
 * this repo's history) would surface late, in whichever migration ships
 * next in this collection.
 *
 * `issue_date` is `unique: true` in the collection but the database column
 * is nullable — Postgres unique indexes permit multiple NULLs (0007's own
 * precedent for `identities.email`), which is exactly right for a draft
 * created before its issue date is decided.
 */
export async function up({ db }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
    CREATE TYPE "public"."enum_editions_status" AS ENUM('draft', 'published');
    CREATE TYPE "public"."enum__editions_v_version_status" AS ENUM('draft', 'published');

    CREATE TABLE "editions" (
      "id" serial PRIMARY KEY NOT NULL,
      "title" varchar,
      "issue_label" varchar,
      "issue_date" timestamp(3) with time zone,
      "cover_id" integer,
      "on_sale_at" timestamp(3) with time zone,
      "sold_out" boolean DEFAULT false,
      "price_idr" numeric,
      "replica_pdf_id" integer,
      "notes" varchar,
      "updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
      "created_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
      "_status" "public"."enum_editions_status" DEFAULT 'draft'
    );

    CREATE TABLE "editions_contents" (
      "_order" integer NOT NULL,
      "_parent_id" integer NOT NULL,
      "id" varchar PRIMARY KEY NOT NULL,
      "heading" varchar,
      "article_id" integer,
      "blurb" varchar
    );

    CREATE TABLE "_editions_v" (
      "id" serial PRIMARY KEY NOT NULL,
      "parent_id" integer,
      "version_title" varchar,
      "version_issue_label" varchar,
      "version_issue_date" timestamp(3) with time zone,
      "version_cover_id" integer,
      "version_on_sale_at" timestamp(3) with time zone,
      "version_sold_out" boolean DEFAULT false,
      "version_price_idr" numeric,
      "version_replica_pdf_id" integer,
      "version_notes" varchar,
      "version_updated_at" timestamp(3) with time zone,
      "version_created_at" timestamp(3) with time zone,
      "version__status" "public"."enum__editions_v_version_status" DEFAULT 'draft',
      "created_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
      "updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL
    );

    CREATE TABLE "_editions_v_version_contents" (
      "_order" integer NOT NULL,
      "_parent_id" integer NOT NULL,
      "id" varchar PRIMARY KEY NOT NULL,
      "heading" varchar,
      "article_id" integer,
      "blurb" varchar
    );

    ALTER TABLE "editions" ADD CONSTRAINT "editions_cover_id_media_id_fk"
      FOREIGN KEY ("cover_id") REFERENCES "media"("id") ON DELETE SET NULL;
    ALTER TABLE "editions" ADD CONSTRAINT "editions_replica_pdf_id_media_id_fk"
      FOREIGN KEY ("replica_pdf_id") REFERENCES "media"("id") ON DELETE SET NULL;

    ALTER TABLE "editions_contents" ADD CONSTRAINT "editions_contents_parent_id_fk"
      FOREIGN KEY ("_parent_id") REFERENCES "editions"("id") ON DELETE CASCADE;
    ALTER TABLE "editions_contents" ADD CONSTRAINT "editions_contents_article_id_articles_id_fk"
      FOREIGN KEY ("article_id") REFERENCES "articles"("id") ON DELETE SET NULL;

    ALTER TABLE "_editions_v" ADD CONSTRAINT "_editions_v_parent_id_editions_id_fk"
      FOREIGN KEY ("parent_id") REFERENCES "editions"("id") ON DELETE SET NULL;
    ALTER TABLE "_editions_v" ADD CONSTRAINT "_editions_v_version_cover_id_media_id_fk"
      FOREIGN KEY ("version_cover_id") REFERENCES "media"("id") ON DELETE SET NULL;
    ALTER TABLE "_editions_v" ADD CONSTRAINT "_editions_v_version_replica_pdf_id_media_id_fk"
      FOREIGN KEY ("version_replica_pdf_id") REFERENCES "media"("id") ON DELETE SET NULL;

    ALTER TABLE "_editions_v_version_contents" ADD CONSTRAINT "_editions_v_version_contents_parent_id_fk"
      FOREIGN KEY ("_parent_id") REFERENCES "_editions_v"("id") ON DELETE CASCADE;
    ALTER TABLE "_editions_v_version_contents" ADD CONSTRAINT "_editions_v_version_contents_article_id_articles_id_fk"
      FOREIGN KEY ("article_id") REFERENCES "articles"("id") ON DELETE SET NULL;

    CREATE UNIQUE INDEX "editions_issue_date_idx" ON "editions" USING btree ("issue_date");
    CREATE INDEX "editions_cover_idx" ON "editions" USING btree ("cover_id");
    CREATE INDEX "editions_replica_pdf_idx" ON "editions" USING btree ("replica_pdf_id");
    CREATE INDEX "editions__status_idx" ON "editions" USING btree ("_status");
    CREATE INDEX "editions_created_at_idx" ON "editions" USING btree ("created_at");
    CREATE INDEX "editions_updated_at_idx" ON "editions" USING btree ("updated_at");

    CREATE INDEX "editions_contents_order_idx" ON "editions_contents" USING btree ("_order");
    CREATE INDEX "editions_contents_parent_id_idx" ON "editions_contents" USING btree ("_parent_id");
    CREATE INDEX "editions_contents_article_idx" ON "editions_contents" USING btree ("article_id");

    CREATE INDEX "_editions_v_parent_idx" ON "_editions_v" USING btree ("parent_id");
    CREATE INDEX "_editions_v_version_version_cover_idx" ON "_editions_v" USING btree ("version_cover_id");
    CREATE INDEX "_editions_v_version_version_replica_pdf_idx" ON "_editions_v" USING btree ("version_replica_pdf_id");
    CREATE INDEX "_editions_v_version_version__status_idx" ON "_editions_v" USING btree ("version__status");
    CREATE INDEX "_editions_v_version_version_created_at_idx" ON "_editions_v" USING btree ("version_created_at");
    CREATE INDEX "_editions_v_version_version_updated_at_idx" ON "_editions_v" USING btree ("version_updated_at");
    CREATE INDEX "_editions_v_created_at_idx" ON "_editions_v" USING btree ("created_at");
    CREATE INDEX "_editions_v_updated_at_idx" ON "_editions_v" USING btree ("updated_at");

    CREATE INDEX "_editions_v_version_contents_order_idx" ON "_editions_v_version_contents" USING btree ("_order");
    CREATE INDEX "_editions_v_version_contents_parent_id_idx" ON "_editions_v_version_contents" USING btree ("_parent_id");
    CREATE INDEX "_editions_v_version_contents_article_idx" ON "_editions_v_version_contents" USING btree ("article_id");
  `)
}

export async function down({ db }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
    DROP TABLE IF EXISTS "_editions_v_version_contents";
    DROP TABLE IF EXISTS "_editions_v";
    DROP TABLE IF EXISTS "editions_contents";
    DROP TABLE IF EXISTS "editions";
    DROP TYPE IF EXISTS "public"."enum__editions_v_version_status";
    DROP TYPE IF EXISTS "public"."enum_editions_status";
  `)
}
