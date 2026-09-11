import { MigrateUpArgs, MigrateDownArgs, sql } from '@payloadcms/db-postgres'

export async function up({ db, payload, req }: MigrateUpArgs): Promise<void> {
  // NOTE (E2.8): `payload migrate:create` also generated four
  // `ALTER TYPE ... ADD VALUE 'unknown' BEFORE 'wellness'` statements here
  // for enum_articles_primary_type / enum__articles_v_version_primary_type /
  // enum_places_type / enum__places_v_version_type. Deliberately removed.
  // Verified against the live now_jakarta DB before deciding this: those
  // enums already contain 'unknown' (F49, migrations
  // 20260909_150000/150100, applied batch 3) — Postgres just appended it at
  // the END of the enum rather than before 'wellness'. drizzle's own
  // snapshot (src/migrations/20260908_131927_initial_schema.json) was never
  // updated by F49's hand-authored raw-SQL migrations, so it still records
  // the original 8-value enum — an F20/F49-adjacent snapshot-drift bug,
  // out of scope for E2.8 to fix, but running these statements as
  // generated would have thrown "42710: type already has value 'unknown'"
  // against every already-migrated city DB. See this ticket's final report.
  await db.execute(sql`
   CREATE TYPE "public"."enum_classification_reviews_entity_type" AS ENUM('article', 'place');
  CREATE TYPE "public"."enum_classification_reviews_facet_key" AS ENUM('type', 'subtype', 'format', 'location');
  CREATE TYPE "public"."enum_classification_reviews_confidence_band" AS ENUM('low', 'medium', 'high');
  CREATE TYPE "public"."enum_classification_reviews_source" AS ENUM('ai', 'editor', 'inferred');
  CREATE TYPE "public"."enum_classification_reviews_review_state" AS ENUM('pending', 'accepted', 'corrected', 'unclassifiable');
  CREATE TABLE "classification_reviews" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"entity_type" "enum_classification_reviews_entity_type",
  	"legacy_category" varchar,
  	"facet_key" "enum_classification_reviews_facet_key" NOT NULL,
  	"term_id" varchar,
  	"proposed_value" varchar NOT NULL,
  	"confidence" numeric NOT NULL,
  	"confidence_band" "enum_classification_reviews_confidence_band",
  	"reasoning" varchar NOT NULL,
  	"source" "enum_classification_reviews_source" DEFAULT 'ai',
  	"weight" numeric DEFAULT 1,
  	"review_state" "enum_classification_reviews_review_state" DEFAULT 'pending' NOT NULL,
  	"final_value" varchar,
  	"reviewed_by_id" integer,
  	"reviewed_at" timestamp(3) with time zone,
  	"site_slug" varchar,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );
  
  CREATE TABLE "classification_reviews_rels" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"order" integer,
  	"parent_id" integer NOT NULL,
  	"path" varchar NOT NULL,
  	"articles_id" integer,
  	"places_id" integer
  );
  
  ALTER TABLE "payload_locked_documents_rels" ADD COLUMN "classification_reviews_id" integer;
  ALTER TABLE "classification_reviews" ADD CONSTRAINT "classification_reviews_reviewed_by_id_users_id_fk" FOREIGN KEY ("reviewed_by_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "classification_reviews_rels" ADD CONSTRAINT "classification_reviews_rels_parent_fk" FOREIGN KEY ("parent_id") REFERENCES "public"."classification_reviews"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "classification_reviews_rels" ADD CONSTRAINT "classification_reviews_rels_articles_fk" FOREIGN KEY ("articles_id") REFERENCES "public"."articles"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "classification_reviews_rels" ADD CONSTRAINT "classification_reviews_rels_places_fk" FOREIGN KEY ("places_id") REFERENCES "public"."places"("id") ON DELETE cascade ON UPDATE no action;
  CREATE INDEX "classification_reviews_reviewed_by_idx" ON "classification_reviews" USING btree ("reviewed_by_id");
  CREATE INDEX "classification_reviews_updated_at_idx" ON "classification_reviews" USING btree ("updated_at");
  CREATE INDEX "classification_reviews_created_at_idx" ON "classification_reviews" USING btree ("created_at");
  CREATE INDEX "classification_reviews_rels_order_idx" ON "classification_reviews_rels" USING btree ("order");
  CREATE INDEX "classification_reviews_rels_parent_idx" ON "classification_reviews_rels" USING btree ("parent_id");
  CREATE INDEX "classification_reviews_rels_path_idx" ON "classification_reviews_rels" USING btree ("path");
  CREATE INDEX "classification_reviews_rels_articles_id_idx" ON "classification_reviews_rels" USING btree ("articles_id");
  CREATE INDEX "classification_reviews_rels_places_id_idx" ON "classification_reviews_rels" USING btree ("places_id");
  ALTER TABLE "payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_classification_reviews_fk" FOREIGN KEY ("classification_reviews_id") REFERENCES "public"."classification_reviews"("id") ON DELETE cascade ON UPDATE no action;
  CREATE INDEX "payload_locked_documents_rels_classification_reviews_id_idx" ON "payload_locked_documents_rels" USING btree ("classification_reviews_id");`)
}

export async function down({ db, payload, req }: MigrateDownArgs): Promise<void> {
  // See the matching note in up(): the generated primary_type/type enum
  // rebuild statements were removed — they were a snapshot-drift artifact,
  // not a real change this migration made, and running them here would
  // have destroyed the real, already-live 'unknown' sentinel (F49).
  await db.execute(sql`
   ALTER TABLE "classification_reviews" DISABLE ROW LEVEL SECURITY;
  ALTER TABLE "classification_reviews_rels" DISABLE ROW LEVEL SECURITY;
  DROP TABLE "classification_reviews" CASCADE;
  DROP TABLE "classification_reviews_rels" CASCADE;
  ALTER TABLE "payload_locked_documents_rels" DROP CONSTRAINT "payload_locked_documents_rels_classification_reviews_fk";
  DROP INDEX "payload_locked_documents_rels_classification_reviews_id_idx";
  ALTER TABLE "payload_locked_documents_rels" DROP COLUMN "classification_reviews_id";
  DROP TYPE "public"."enum_classification_reviews_entity_type";
  DROP TYPE "public"."enum_classification_reviews_facet_key";
  DROP TYPE "public"."enum_classification_reviews_confidence_band";
  DROP TYPE "public"."enum_classification_reviews_source";
  DROP TYPE "public"."enum_classification_reviews_review_state";`)
}
