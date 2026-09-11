import { MigrateUpArgs, MigrateDownArgs, sql } from '@payloadcms/db-postgres'

export async function up({ db, payload, req }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
   ALTER TABLE "events" ADD COLUMN "title" varchar DEFAULT 'Untitled event';
  ALTER TABLE "events" ADD COLUMN "dek" varchar;
  ALTER TABLE "events" ADD COLUMN "body_blocks" jsonb;
  ALTER TABLE "events" ADD COLUMN "hero_media_id" integer;
  ALTER TABLE "events" ADD COLUMN "article_id" integer;
  ALTER TABLE "events" ADD COLUMN "legacy_wp_id" numeric;
  ALTER TABLE "_events_v" ADD COLUMN "version_title" varchar DEFAULT 'Untitled event';
  ALTER TABLE "_events_v" ADD COLUMN "version_dek" varchar;
  ALTER TABLE "_events_v" ADD COLUMN "version_body_blocks" jsonb;
  ALTER TABLE "_events_v" ADD COLUMN "version_hero_media_id" integer;
  ALTER TABLE "_events_v" ADD COLUMN "version_article_id" integer;
  ALTER TABLE "_events_v" ADD COLUMN "version_legacy_wp_id" numeric;
  ALTER TABLE "events" ADD CONSTRAINT "events_hero_media_id_media_id_fk" FOREIGN KEY ("hero_media_id") REFERENCES "public"."media"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "events" ADD CONSTRAINT "events_article_id_articles_id_fk" FOREIGN KEY ("article_id") REFERENCES "public"."articles"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "_events_v" ADD CONSTRAINT "_events_v_version_hero_media_id_media_id_fk" FOREIGN KEY ("version_hero_media_id") REFERENCES "public"."media"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "_events_v" ADD CONSTRAINT "_events_v_version_article_id_articles_id_fk" FOREIGN KEY ("version_article_id") REFERENCES "public"."articles"("id") ON DELETE set null ON UPDATE no action;
  CREATE INDEX "events_hero_media_idx" ON "events" USING btree ("hero_media_id");
  CREATE INDEX "events_article_idx" ON "events" USING btree ("article_id");
  CREATE UNIQUE INDEX "events_legacy_wp_id_idx" ON "events" USING btree ("legacy_wp_id");
  CREATE INDEX "_events_v_version_version_hero_media_idx" ON "_events_v" USING btree ("version_hero_media_id");
  CREATE INDEX "_events_v_version_version_article_idx" ON "_events_v" USING btree ("version_article_id");
  CREATE INDEX "_events_v_version_version_legacy_wp_id_idx" ON "_events_v" USING btree ("version_legacy_wp_id");`)
}

export async function down({ db, payload, req }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
   ALTER TABLE "events" DROP CONSTRAINT "events_hero_media_id_media_id_fk";
  
  ALTER TABLE "events" DROP CONSTRAINT "events_article_id_articles_id_fk";
  
  ALTER TABLE "_events_v" DROP CONSTRAINT "_events_v_version_hero_media_id_media_id_fk";
  
  ALTER TABLE "_events_v" DROP CONSTRAINT "_events_v_version_article_id_articles_id_fk";
  
  DROP INDEX "events_hero_media_idx";
  DROP INDEX "events_article_idx";
  DROP INDEX "events_legacy_wp_id_idx";
  DROP INDEX "_events_v_version_version_hero_media_idx";
  DROP INDEX "_events_v_version_version_article_idx";
  DROP INDEX "_events_v_version_version_legacy_wp_id_idx";
  ALTER TABLE "events" DROP COLUMN "title";
  ALTER TABLE "events" DROP COLUMN "dek";
  ALTER TABLE "events" DROP COLUMN "body_blocks";
  ALTER TABLE "events" DROP COLUMN "hero_media_id";
  ALTER TABLE "events" DROP COLUMN "article_id";
  ALTER TABLE "events" DROP COLUMN "legacy_wp_id";
  ALTER TABLE "_events_v" DROP COLUMN "version_title";
  ALTER TABLE "_events_v" DROP COLUMN "version_dek";
  ALTER TABLE "_events_v" DROP COLUMN "version_body_blocks";
  ALTER TABLE "_events_v" DROP COLUMN "version_hero_media_id";
  ALTER TABLE "_events_v" DROP COLUMN "version_article_id";
  ALTER TABLE "_events_v" DROP COLUMN "version_legacy_wp_id";`)
}
