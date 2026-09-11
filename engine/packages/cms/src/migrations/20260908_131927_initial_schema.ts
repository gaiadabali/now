import { MigrateUpArgs, MigrateDownArgs, sql } from '@payloadcms/db-postgres'

export async function up({ db, payload, req }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
   CREATE TYPE "public"."enum_articles_kind" AS ENUM('article', 'guide', 'itinerary_narrative');
  CREATE TYPE "public"."enum_articles_primary_type" AS ENUM('do', 'drink', 'eat', 'editorial', 'event', 'shop', 'stay', 'wellness');
  CREATE TYPE "public"."enum_articles_format" AS ENUM('city-guide', 'event', 'feature', 'guide', 'heritage', 'listing', 'news', 'offer', 'opinion', 'people', 'review');
  CREATE TYPE "public"."enum_articles_status" AS ENUM('draft', 'published');
  CREATE TYPE "public"."enum__articles_v_version_kind" AS ENUM('article', 'guide', 'itinerary_narrative');
  CREATE TYPE "public"."enum__articles_v_version_primary_type" AS ENUM('do', 'drink', 'eat', 'editorial', 'event', 'shop', 'stay', 'wellness');
  CREATE TYPE "public"."enum__articles_v_version_format" AS ENUM('city-guide', 'event', 'feature', 'guide', 'heritage', 'listing', 'news', 'offer', 'opinion', 'people', 'review');
  CREATE TYPE "public"."enum__articles_v_version_status" AS ENUM('draft', 'published');
  CREATE TYPE "public"."enum_places_cuisine" AS ENUM('american', 'asian-fusion', 'balinese', 'betawi', 'chinese', 'european', 'french', 'indian', 'indonesian', 'italian', 'japanese', 'javanese', 'korean', 'latin-american', 'manadonese', 'mediterranean', 'mexican', 'middle-eastern', 'padang', 'peranakan', 'seafood', 'spanish', 'steakhouse', 'sundanese', 'thai', 'vietnamese', 'western');
  CREATE TYPE "public"."enum_places_amenities" AS ENUM('beachfront', 'city-view', 'coworking-space', 'garden', 'gym', 'halal-certified', 'kids-club', 'live-music', 'ocean-view', 'outdoor-seating', 'parking', 'pet-friendly', 'pool', 'private-dining', 'rooftop', 'spa', 'valet', 'vegan-options', 'vegetarian-friendly', 'wheelchair-accessible', 'wifi');
  CREATE TYPE "public"."enum_places_vibe" AS ENUM('artsy', 'casual', 'classic', 'cozy', 'hidden-gem', 'instagrammable', 'laid-back', 'lively', 'luxury', 'party', 'romantic', 'scenic', 'serene', 'trendy');
  CREATE TYPE "public"."enum_places_hours_day" AS ENUM('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun');
  CREATE TYPE "public"."enum_places_area_term" AS ENUM('alam-sutera', 'amed', 'ancol', 'bali', 'bandung', 'banyuwangi', 'bekasi', 'belitung', 'bintan', 'bintaro', 'blok-m', 'bogor', 'bsd', 'candidasa', 'canggu', 'central-bali', 'central-jakarta', 'cibubur', 'cikini', 'cipete', 'denpasar', 'depok', 'east-bali', 'east-jakarta', 'other', 'gading-serpong', 'gambir', 'glodok', 'greater-jakarta', 'gunawarman', 'indonesia', 'international', 'jakarta', 'jimbaran', 'kebon-jeruk', 'kelapa-gading', 'kemang', 'kerobokan', 'komodo', 'kota-tua', 'kuningan', 'kuta', 'lake-toba', 'legian', 'lombok', 'lovina', 'makassar', 'malang', 'manado', 'medan', 'menteng', 'north-bali', 'north-jakarta', 'nusa-dua', 'nusa-penida', 'pasar-baru', 'pererenan', 'pik', 'pondok-indah', 'puncak', 'puri-indah', 'raja-ampat', 'rawamangun', 'sanur', 'scbd', 'semarang', 'seminyak', 'senayan', 'senopati', 'sentul', 'sidemen', 'solo', 'south-bali', 'south-jakarta', 'sudirman', 'sumba', 'surabaya', 'tangerang', 'tebet', 'thamrin', 'toraja', 'ubud', 'uluwatu', 'west-jakarta', 'yogyakarta');
  CREATE TYPE "public"."enum_places_type" AS ENUM('do', 'drink', 'eat', 'editorial', 'event', 'shop', 'stay', 'wellness');
  CREATE TYPE "public"."enum_places_subtype" AS ENUM('adventure', 'artisan', 'attraction', 'bakery', 'bar', 'beach-club', 'boutique', 'boutique-hotel', 'business', 'cafe', 'city-guide', 'clinic', 'cocktail-bar', 'community', 'concert', 'conference', 'culture', 'education', 'exhibition', 'festival', 'fine-dining', 'food-court', 'gallery', 'glamping', 'gym', 'heritage', 'hotel', 'lifestyle', 'mall', 'market', 'museum', 'news', 'nightclub', 'opinion', 'people', 'performance', 'pop-up', 'pub', 'resort', 'restaurant', 'retreat', 'rooftop-bar', 'salon', 'screening', 'serviced-apartment', 'spa', 'sports', 'sports-activity', 'street-food', 'tour', 'villa', 'watersports', 'wine-bar', 'workshop', 'yoga');
  CREATE TYPE "public"."enum_places_price_band" AS ENUM('budget', 'moderate', 'upscale', 'luxury');
  CREATE TYPE "public"."enum_places_status" AS ENUM('active', 'closed', 'pending_review');
  CREATE TYPE "public"."enum__places_v_version_cuisine" AS ENUM('american', 'asian-fusion', 'balinese', 'betawi', 'chinese', 'european', 'french', 'indian', 'indonesian', 'italian', 'japanese', 'javanese', 'korean', 'latin-american', 'manadonese', 'mediterranean', 'mexican', 'middle-eastern', 'padang', 'peranakan', 'seafood', 'spanish', 'steakhouse', 'sundanese', 'thai', 'vietnamese', 'western');
  CREATE TYPE "public"."enum__places_v_version_amenities" AS ENUM('beachfront', 'city-view', 'coworking-space', 'garden', 'gym', 'halal-certified', 'kids-club', 'live-music', 'ocean-view', 'outdoor-seating', 'parking', 'pet-friendly', 'pool', 'private-dining', 'rooftop', 'spa', 'valet', 'vegan-options', 'vegetarian-friendly', 'wheelchair-accessible', 'wifi');
  CREATE TYPE "public"."enum__places_v_version_vibe" AS ENUM('artsy', 'casual', 'classic', 'cozy', 'hidden-gem', 'instagrammable', 'laid-back', 'lively', 'luxury', 'party', 'romantic', 'scenic', 'serene', 'trendy');
  CREATE TYPE "public"."enum__places_v_version_hours_day" AS ENUM('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun');
  CREATE TYPE "public"."enum__places_v_version_area_term" AS ENUM('alam-sutera', 'amed', 'ancol', 'bali', 'bandung', 'banyuwangi', 'bekasi', 'belitung', 'bintan', 'bintaro', 'blok-m', 'bogor', 'bsd', 'candidasa', 'canggu', 'central-bali', 'central-jakarta', 'cibubur', 'cikini', 'cipete', 'denpasar', 'depok', 'east-bali', 'east-jakarta', 'other', 'gading-serpong', 'gambir', 'glodok', 'greater-jakarta', 'gunawarman', 'indonesia', 'international', 'jakarta', 'jimbaran', 'kebon-jeruk', 'kelapa-gading', 'kemang', 'kerobokan', 'komodo', 'kota-tua', 'kuningan', 'kuta', 'lake-toba', 'legian', 'lombok', 'lovina', 'makassar', 'malang', 'manado', 'medan', 'menteng', 'north-bali', 'north-jakarta', 'nusa-dua', 'nusa-penida', 'pasar-baru', 'pererenan', 'pik', 'pondok-indah', 'puncak', 'puri-indah', 'raja-ampat', 'rawamangun', 'sanur', 'scbd', 'semarang', 'seminyak', 'senayan', 'senopati', 'sentul', 'sidemen', 'solo', 'south-bali', 'south-jakarta', 'sudirman', 'sumba', 'surabaya', 'tangerang', 'tebet', 'thamrin', 'toraja', 'ubud', 'uluwatu', 'west-jakarta', 'yogyakarta');
  CREATE TYPE "public"."enum__places_v_version_type" AS ENUM('do', 'drink', 'eat', 'editorial', 'event', 'shop', 'stay', 'wellness');
  CREATE TYPE "public"."enum__places_v_version_subtype" AS ENUM('adventure', 'artisan', 'attraction', 'bakery', 'bar', 'beach-club', 'boutique', 'boutique-hotel', 'business', 'cafe', 'city-guide', 'clinic', 'cocktail-bar', 'community', 'concert', 'conference', 'culture', 'education', 'exhibition', 'festival', 'fine-dining', 'food-court', 'gallery', 'glamping', 'gym', 'heritage', 'hotel', 'lifestyle', 'mall', 'market', 'museum', 'news', 'nightclub', 'opinion', 'people', 'performance', 'pop-up', 'pub', 'resort', 'restaurant', 'retreat', 'rooftop-bar', 'salon', 'screening', 'serviced-apartment', 'spa', 'sports', 'sports-activity', 'street-food', 'tour', 'villa', 'watersports', 'wine-bar', 'workshop', 'yoga');
  CREATE TYPE "public"."enum__places_v_version_price_band" AS ENUM('budget', 'moderate', 'upscale', 'luxury');
  CREATE TYPE "public"."enum__places_v_version_status" AS ENUM('active', 'closed', 'pending_review');
  CREATE TYPE "public"."enum_events_status" AS ENUM('draft', 'published');
  CREATE TYPE "public"."enum__events_v_version_status" AS ENUM('draft', 'published');
  CREATE TYPE "public"."enum_place_mentions_role" AS ENUM('mentioned', 'featured', 'reviewed');
  CREATE TYPE "public"."enum_users_role" AS ENUM('admin', 'editor', 'author');
  CREATE TYPE "public"."enum_payload_jobs_log_task_slug" AS ENUM('inline', 'schedulePublish');
  CREATE TYPE "public"."enum_payload_jobs_log_state" AS ENUM('failed', 'succeeded');
  CREATE TYPE "public"."enum_payload_jobs_task_slug" AS ENUM('inline', 'schedulePublish');
  CREATE TABLE "articles" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"kind" "enum_articles_kind" DEFAULT 'article',
  	"title" varchar,
  	"dek" varchar,
  	"body_blocks" jsonb,
  	"hero_media_id" integer,
  	"author_id" integer,
  	"primary_type" "enum_articles_primary_type",
  	"format" "enum_articles_format",
  	"published_at" timestamp(3) with time zone,
  	"legacy_wp_id" numeric,
  	"legacy_permalink" varchar,
  	"series_key" varchar,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"_status" "enum_articles_status" DEFAULT 'draft'
  );
  
  CREATE TABLE "_articles_v" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"parent_id" integer,
  	"version_kind" "enum__articles_v_version_kind" DEFAULT 'article',
  	"version_title" varchar,
  	"version_dek" varchar,
  	"version_body_blocks" jsonb,
  	"version_hero_media_id" integer,
  	"version_author_id" integer,
  	"version_primary_type" "enum__articles_v_version_primary_type",
  	"version_format" "enum__articles_v_version_format",
  	"version_published_at" timestamp(3) with time zone,
  	"version_legacy_wp_id" numeric,
  	"version_legacy_permalink" varchar,
  	"version_series_key" varchar,
  	"version_updated_at" timestamp(3) with time zone,
  	"version_created_at" timestamp(3) with time zone,
  	"version__status" "enum__articles_v_version_status" DEFAULT 'draft',
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"latest" boolean,
  	"autosave" boolean
  );
  
  CREATE TABLE "places_cuisine" (
  	"order" integer NOT NULL,
  	"parent_id" integer NOT NULL,
  	"value" "enum_places_cuisine",
  	"id" serial PRIMARY KEY NOT NULL
  );
  
  CREATE TABLE "places_amenities" (
  	"order" integer NOT NULL,
  	"parent_id" integer NOT NULL,
  	"value" "enum_places_amenities",
  	"id" serial PRIMARY KEY NOT NULL
  );
  
  CREATE TABLE "places_vibe" (
  	"order" integer NOT NULL,
  	"parent_id" integer NOT NULL,
  	"value" "enum_places_vibe",
  	"id" serial PRIMARY KEY NOT NULL
  );
  
  CREATE TABLE "places_hours" (
  	"_order" integer NOT NULL,
  	"_parent_id" integer NOT NULL,
  	"id" varchar PRIMARY KEY NOT NULL,
  	"day" "enum_places_hours_day" NOT NULL,
  	"opens" varchar,
  	"closes" varchar
  );
  
  CREATE TABLE "places" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"name" varchar NOT NULL,
  	"slug" varchar NOT NULL,
  	"org_id" varchar,
  	"lat" numeric,
  	"lng" numeric,
  	"address" varchar,
  	"area_term" "enum_places_area_term",
  	"type" "enum_places_type" NOT NULL,
  	"subtype" "enum_places_subtype" NOT NULL,
  	"price_band" "enum_places_price_band",
  	"avg_dwell_min" numeric,
  	"booking_url" varchar,
  	"google_place_id" varchar,
  	"status" "enum_places_status" DEFAULT 'active' NOT NULL,
  	"verified_at" timestamp(3) with time zone,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );
  
  CREATE TABLE "_places_v_version_cuisine" (
  	"order" integer NOT NULL,
  	"parent_id" integer NOT NULL,
  	"value" "enum__places_v_version_cuisine",
  	"id" serial PRIMARY KEY NOT NULL
  );
  
  CREATE TABLE "_places_v_version_amenities" (
  	"order" integer NOT NULL,
  	"parent_id" integer NOT NULL,
  	"value" "enum__places_v_version_amenities",
  	"id" serial PRIMARY KEY NOT NULL
  );
  
  CREATE TABLE "_places_v_version_vibe" (
  	"order" integer NOT NULL,
  	"parent_id" integer NOT NULL,
  	"value" "enum__places_v_version_vibe",
  	"id" serial PRIMARY KEY NOT NULL
  );
  
  CREATE TABLE "_places_v_version_hours" (
  	"_order" integer NOT NULL,
  	"_parent_id" integer NOT NULL,
  	"id" serial PRIMARY KEY NOT NULL,
  	"day" "enum__places_v_version_hours_day" NOT NULL,
  	"opens" varchar,
  	"closes" varchar,
  	"_uuid" varchar
  );
  
  CREATE TABLE "_places_v" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"parent_id" integer,
  	"version_name" varchar NOT NULL,
  	"version_slug" varchar NOT NULL,
  	"version_org_id" varchar,
  	"version_lat" numeric,
  	"version_lng" numeric,
  	"version_address" varchar,
  	"version_area_term" "enum__places_v_version_area_term",
  	"version_type" "enum__places_v_version_type" NOT NULL,
  	"version_subtype" "enum__places_v_version_subtype" NOT NULL,
  	"version_price_band" "enum__places_v_version_price_band",
  	"version_avg_dwell_min" numeric,
  	"version_booking_url" varchar,
  	"version_google_place_id" varchar,
  	"version_status" "enum__places_v_version_status" DEFAULT 'active' NOT NULL,
  	"version_verified_at" timestamp(3) with time zone,
  	"version_updated_at" timestamp(3) with time zone,
  	"version_created_at" timestamp(3) with time zone,
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );
  
  CREATE TABLE "events" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"place_id" integer,
  	"starts_at" timestamp(3) with time zone,
  	"ends_at" timestamp(3) with time zone,
  	"rrule" varchar,
  	"ticket_url" varchar,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"_status" "enum_events_status" DEFAULT 'draft'
  );
  
  CREATE TABLE "_events_v" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"parent_id" integer,
  	"version_place_id" integer,
  	"version_starts_at" timestamp(3) with time zone,
  	"version_ends_at" timestamp(3) with time zone,
  	"version_rrule" varchar,
  	"version_ticket_url" varchar,
  	"version_updated_at" timestamp(3) with time zone,
  	"version_created_at" timestamp(3) with time zone,
  	"version__status" "enum__events_v_version_status" DEFAULT 'draft',
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"latest" boolean
  );
  
  CREATE TABLE "place_mentions" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"article_id" integer NOT NULL,
  	"place_id" integer NOT NULL,
  	"offset" numeric,
  	"surface_text" varchar NOT NULL,
  	"role" "enum_place_mentions_role" DEFAULT 'mentioned',
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );
  
  CREATE TABLE "media" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"alt" varchar NOT NULL,
  	"credit" varchar,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"url" varchar,
  	"thumbnail_u_r_l" varchar,
  	"filename" varchar,
  	"mime_type" varchar,
  	"filesize" numeric,
  	"width" numeric,
  	"height" numeric,
  	"focal_x" numeric,
  	"focal_y" numeric,
  	"sizes_thumbnail_url" varchar,
  	"sizes_thumbnail_width" numeric,
  	"sizes_thumbnail_height" numeric,
  	"sizes_thumbnail_mime_type" varchar,
  	"sizes_thumbnail_filesize" numeric,
  	"sizes_thumbnail_filename" varchar,
  	"sizes_card_url" varchar,
  	"sizes_card_width" numeric,
  	"sizes_card_height" numeric,
  	"sizes_card_mime_type" varchar,
  	"sizes_card_filesize" numeric,
  	"sizes_card_filename" varchar,
  	"sizes_hero_url" varchar,
  	"sizes_hero_width" numeric,
  	"sizes_hero_height" numeric,
  	"sizes_hero_mime_type" varchar,
  	"sizes_hero_filesize" numeric,
  	"sizes_hero_filename" varchar
  );
  
  CREATE TABLE "authors" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"name" varchar NOT NULL,
  	"slug" varchar NOT NULL,
  	"bio" varchar,
  	"avatar_id" integer,
  	"legacy_wp_user_id" numeric,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );
  
  CREATE TABLE "users_sessions" (
  	"_order" integer NOT NULL,
  	"_parent_id" integer NOT NULL,
  	"id" varchar PRIMARY KEY NOT NULL,
  	"created_at" timestamp(3) with time zone,
  	"expires_at" timestamp(3) with time zone NOT NULL
  );
  
  CREATE TABLE "users" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"role" "enum_users_role" DEFAULT 'author' NOT NULL,
  	"name" varchar,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"email" varchar NOT NULL,
  	"reset_password_token" varchar,
  	"reset_password_expiration" timestamp(3) with time zone,
  	"salt" varchar,
  	"hash" varchar,
  	"login_attempts" numeric DEFAULT 0,
  	"lock_until" timestamp(3) with time zone
  );
  
  CREATE TABLE "payload_kv" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"key" varchar NOT NULL,
  	"data" jsonb NOT NULL
  );
  
  CREATE TABLE "payload_jobs_log" (
  	"_order" integer NOT NULL,
  	"_parent_id" integer NOT NULL,
  	"id" varchar PRIMARY KEY NOT NULL,
  	"executed_at" timestamp(3) with time zone NOT NULL,
  	"completed_at" timestamp(3) with time zone NOT NULL,
  	"task_slug" "enum_payload_jobs_log_task_slug" NOT NULL,
  	"task_i_d" varchar NOT NULL,
  	"input" jsonb,
  	"output" jsonb,
  	"state" "enum_payload_jobs_log_state" NOT NULL,
  	"error" jsonb
  );
  
  CREATE TABLE "payload_jobs" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"input" jsonb,
  	"completed_at" timestamp(3) with time zone,
  	"total_tried" numeric DEFAULT 0,
  	"has_error" boolean DEFAULT false,
  	"error" jsonb,
  	"task_slug" "enum_payload_jobs_task_slug",
  	"queue" varchar DEFAULT 'default',
  	"wait_until" timestamp(3) with time zone,
  	"processing" boolean DEFAULT false,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );
  
  CREATE TABLE "payload_locked_documents" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"global_slug" varchar,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );
  
  CREATE TABLE "payload_locked_documents_rels" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"order" integer,
  	"parent_id" integer NOT NULL,
  	"path" varchar NOT NULL,
  	"articles_id" integer,
  	"places_id" integer,
  	"events_id" integer,
  	"place_mentions_id" integer,
  	"media_id" integer,
  	"authors_id" integer,
  	"users_id" integer
  );
  
  CREATE TABLE "payload_preferences" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"key" varchar,
  	"value" jsonb,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );
  
  CREATE TABLE "payload_preferences_rels" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"order" integer,
  	"parent_id" integer NOT NULL,
  	"path" varchar NOT NULL,
  	"users_id" integer
  );
  
  CREATE TABLE "payload_migrations" (
  	"id" serial PRIMARY KEY NOT NULL,
  	"name" varchar,
  	"batch" numeric,
  	"updated_at" timestamp(3) with time zone DEFAULT now() NOT NULL,
  	"created_at" timestamp(3) with time zone DEFAULT now() NOT NULL
  );
  
  ALTER TABLE "articles" ADD CONSTRAINT "articles_hero_media_id_media_id_fk" FOREIGN KEY ("hero_media_id") REFERENCES "public"."media"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "articles" ADD CONSTRAINT "articles_author_id_authors_id_fk" FOREIGN KEY ("author_id") REFERENCES "public"."authors"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "_articles_v" ADD CONSTRAINT "_articles_v_parent_id_articles_id_fk" FOREIGN KEY ("parent_id") REFERENCES "public"."articles"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "_articles_v" ADD CONSTRAINT "_articles_v_version_hero_media_id_media_id_fk" FOREIGN KEY ("version_hero_media_id") REFERENCES "public"."media"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "_articles_v" ADD CONSTRAINT "_articles_v_version_author_id_authors_id_fk" FOREIGN KEY ("version_author_id") REFERENCES "public"."authors"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "places_cuisine" ADD CONSTRAINT "places_cuisine_parent_fk" FOREIGN KEY ("parent_id") REFERENCES "public"."places"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "places_amenities" ADD CONSTRAINT "places_amenities_parent_fk" FOREIGN KEY ("parent_id") REFERENCES "public"."places"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "places_vibe" ADD CONSTRAINT "places_vibe_parent_fk" FOREIGN KEY ("parent_id") REFERENCES "public"."places"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "places_hours" ADD CONSTRAINT "places_hours_parent_id_fk" FOREIGN KEY ("_parent_id") REFERENCES "public"."places"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "_places_v_version_cuisine" ADD CONSTRAINT "_places_v_version_cuisine_parent_fk" FOREIGN KEY ("parent_id") REFERENCES "public"."_places_v"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "_places_v_version_amenities" ADD CONSTRAINT "_places_v_version_amenities_parent_fk" FOREIGN KEY ("parent_id") REFERENCES "public"."_places_v"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "_places_v_version_vibe" ADD CONSTRAINT "_places_v_version_vibe_parent_fk" FOREIGN KEY ("parent_id") REFERENCES "public"."_places_v"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "_places_v_version_hours" ADD CONSTRAINT "_places_v_version_hours_parent_id_fk" FOREIGN KEY ("_parent_id") REFERENCES "public"."_places_v"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "_places_v" ADD CONSTRAINT "_places_v_parent_id_places_id_fk" FOREIGN KEY ("parent_id") REFERENCES "public"."places"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "events" ADD CONSTRAINT "events_place_id_places_id_fk" FOREIGN KEY ("place_id") REFERENCES "public"."places"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "_events_v" ADD CONSTRAINT "_events_v_parent_id_events_id_fk" FOREIGN KEY ("parent_id") REFERENCES "public"."events"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "_events_v" ADD CONSTRAINT "_events_v_version_place_id_places_id_fk" FOREIGN KEY ("version_place_id") REFERENCES "public"."places"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "place_mentions" ADD CONSTRAINT "place_mentions_article_id_articles_id_fk" FOREIGN KEY ("article_id") REFERENCES "public"."articles"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "place_mentions" ADD CONSTRAINT "place_mentions_place_id_places_id_fk" FOREIGN KEY ("place_id") REFERENCES "public"."places"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "authors" ADD CONSTRAINT "authors_avatar_id_media_id_fk" FOREIGN KEY ("avatar_id") REFERENCES "public"."media"("id") ON DELETE set null ON UPDATE no action;
  ALTER TABLE "users_sessions" ADD CONSTRAINT "users_sessions_parent_id_fk" FOREIGN KEY ("_parent_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "payload_jobs_log" ADD CONSTRAINT "payload_jobs_log_parent_id_fk" FOREIGN KEY ("_parent_id") REFERENCES "public"."payload_jobs"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_parent_fk" FOREIGN KEY ("parent_id") REFERENCES "public"."payload_locked_documents"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_articles_fk" FOREIGN KEY ("articles_id") REFERENCES "public"."articles"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_places_fk" FOREIGN KEY ("places_id") REFERENCES "public"."places"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_events_fk" FOREIGN KEY ("events_id") REFERENCES "public"."events"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_place_mentions_fk" FOREIGN KEY ("place_mentions_id") REFERENCES "public"."place_mentions"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_media_fk" FOREIGN KEY ("media_id") REFERENCES "public"."media"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_authors_fk" FOREIGN KEY ("authors_id") REFERENCES "public"."authors"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "payload_locked_documents_rels" ADD CONSTRAINT "payload_locked_documents_rels_users_fk" FOREIGN KEY ("users_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "payload_preferences_rels" ADD CONSTRAINT "payload_preferences_rels_parent_fk" FOREIGN KEY ("parent_id") REFERENCES "public"."payload_preferences"("id") ON DELETE cascade ON UPDATE no action;
  ALTER TABLE "payload_preferences_rels" ADD CONSTRAINT "payload_preferences_rels_users_fk" FOREIGN KEY ("users_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;
  CREATE INDEX "articles_hero_media_idx" ON "articles" USING btree ("hero_media_id");
  CREATE INDEX "articles_author_idx" ON "articles" USING btree ("author_id");
  CREATE UNIQUE INDEX "articles_legacy_wp_id_idx" ON "articles" USING btree ("legacy_wp_id");
  CREATE INDEX "articles_legacy_permalink_idx" ON "articles" USING btree ("legacy_permalink");
  CREATE INDEX "articles_series_key_idx" ON "articles" USING btree ("series_key");
  CREATE INDEX "articles_updated_at_idx" ON "articles" USING btree ("updated_at");
  CREATE INDEX "articles_created_at_idx" ON "articles" USING btree ("created_at");
  CREATE INDEX "articles__status_idx" ON "articles" USING btree ("_status");
  CREATE INDEX "_articles_v_parent_idx" ON "_articles_v" USING btree ("parent_id");
  CREATE INDEX "_articles_v_version_version_hero_media_idx" ON "_articles_v" USING btree ("version_hero_media_id");
  CREATE INDEX "_articles_v_version_version_author_idx" ON "_articles_v" USING btree ("version_author_id");
  CREATE INDEX "_articles_v_version_version_legacy_wp_id_idx" ON "_articles_v" USING btree ("version_legacy_wp_id");
  CREATE INDEX "_articles_v_version_version_legacy_permalink_idx" ON "_articles_v" USING btree ("version_legacy_permalink");
  CREATE INDEX "_articles_v_version_version_series_key_idx" ON "_articles_v" USING btree ("version_series_key");
  CREATE INDEX "_articles_v_version_version_updated_at_idx" ON "_articles_v" USING btree ("version_updated_at");
  CREATE INDEX "_articles_v_version_version_created_at_idx" ON "_articles_v" USING btree ("version_created_at");
  CREATE INDEX "_articles_v_version_version__status_idx" ON "_articles_v" USING btree ("version__status");
  CREATE INDEX "_articles_v_created_at_idx" ON "_articles_v" USING btree ("created_at");
  CREATE INDEX "_articles_v_updated_at_idx" ON "_articles_v" USING btree ("updated_at");
  CREATE INDEX "_articles_v_latest_idx" ON "_articles_v" USING btree ("latest");
  CREATE INDEX "_articles_v_autosave_idx" ON "_articles_v" USING btree ("autosave");
  CREATE INDEX "places_cuisine_order_idx" ON "places_cuisine" USING btree ("order");
  CREATE INDEX "places_cuisine_parent_idx" ON "places_cuisine" USING btree ("parent_id");
  CREATE INDEX "places_amenities_order_idx" ON "places_amenities" USING btree ("order");
  CREATE INDEX "places_amenities_parent_idx" ON "places_amenities" USING btree ("parent_id");
  CREATE INDEX "places_vibe_order_idx" ON "places_vibe" USING btree ("order");
  CREATE INDEX "places_vibe_parent_idx" ON "places_vibe" USING btree ("parent_id");
  CREATE INDEX "places_hours_order_idx" ON "places_hours" USING btree ("_order");
  CREATE INDEX "places_hours_parent_id_idx" ON "places_hours" USING btree ("_parent_id");
  CREATE UNIQUE INDEX "places_slug_idx" ON "places" USING btree ("slug");
  CREATE INDEX "places_updated_at_idx" ON "places" USING btree ("updated_at");
  CREATE INDEX "places_created_at_idx" ON "places" USING btree ("created_at");
  CREATE INDEX "_places_v_version_cuisine_order_idx" ON "_places_v_version_cuisine" USING btree ("order");
  CREATE INDEX "_places_v_version_cuisine_parent_idx" ON "_places_v_version_cuisine" USING btree ("parent_id");
  CREATE INDEX "_places_v_version_amenities_order_idx" ON "_places_v_version_amenities" USING btree ("order");
  CREATE INDEX "_places_v_version_amenities_parent_idx" ON "_places_v_version_amenities" USING btree ("parent_id");
  CREATE INDEX "_places_v_version_vibe_order_idx" ON "_places_v_version_vibe" USING btree ("order");
  CREATE INDEX "_places_v_version_vibe_parent_idx" ON "_places_v_version_vibe" USING btree ("parent_id");
  CREATE INDEX "_places_v_version_hours_order_idx" ON "_places_v_version_hours" USING btree ("_order");
  CREATE INDEX "_places_v_version_hours_parent_id_idx" ON "_places_v_version_hours" USING btree ("_parent_id");
  CREATE INDEX "_places_v_parent_idx" ON "_places_v" USING btree ("parent_id");
  CREATE INDEX "_places_v_version_version_slug_idx" ON "_places_v" USING btree ("version_slug");
  CREATE INDEX "_places_v_version_version_updated_at_idx" ON "_places_v" USING btree ("version_updated_at");
  CREATE INDEX "_places_v_version_version_created_at_idx" ON "_places_v" USING btree ("version_created_at");
  CREATE INDEX "_places_v_created_at_idx" ON "_places_v" USING btree ("created_at");
  CREATE INDEX "_places_v_updated_at_idx" ON "_places_v" USING btree ("updated_at");
  CREATE INDEX "events_place_idx" ON "events" USING btree ("place_id");
  CREATE INDEX "events_updated_at_idx" ON "events" USING btree ("updated_at");
  CREATE INDEX "events_created_at_idx" ON "events" USING btree ("created_at");
  CREATE INDEX "events__status_idx" ON "events" USING btree ("_status");
  CREATE INDEX "_events_v_parent_idx" ON "_events_v" USING btree ("parent_id");
  CREATE INDEX "_events_v_version_version_place_idx" ON "_events_v" USING btree ("version_place_id");
  CREATE INDEX "_events_v_version_version_updated_at_idx" ON "_events_v" USING btree ("version_updated_at");
  CREATE INDEX "_events_v_version_version_created_at_idx" ON "_events_v" USING btree ("version_created_at");
  CREATE INDEX "_events_v_version_version__status_idx" ON "_events_v" USING btree ("version__status");
  CREATE INDEX "_events_v_created_at_idx" ON "_events_v" USING btree ("created_at");
  CREATE INDEX "_events_v_updated_at_idx" ON "_events_v" USING btree ("updated_at");
  CREATE INDEX "_events_v_latest_idx" ON "_events_v" USING btree ("latest");
  CREATE INDEX "place_mentions_article_idx" ON "place_mentions" USING btree ("article_id");
  CREATE INDEX "place_mentions_place_idx" ON "place_mentions" USING btree ("place_id");
  CREATE INDEX "place_mentions_updated_at_idx" ON "place_mentions" USING btree ("updated_at");
  CREATE INDEX "place_mentions_created_at_idx" ON "place_mentions" USING btree ("created_at");
  CREATE INDEX "media_updated_at_idx" ON "media" USING btree ("updated_at");
  CREATE INDEX "media_created_at_idx" ON "media" USING btree ("created_at");
  CREATE UNIQUE INDEX "media_filename_idx" ON "media" USING btree ("filename");
  CREATE INDEX "media_sizes_thumbnail_sizes_thumbnail_filename_idx" ON "media" USING btree ("sizes_thumbnail_filename");
  CREATE INDEX "media_sizes_card_sizes_card_filename_idx" ON "media" USING btree ("sizes_card_filename");
  CREATE INDEX "media_sizes_hero_sizes_hero_filename_idx" ON "media" USING btree ("sizes_hero_filename");
  CREATE UNIQUE INDEX "authors_slug_idx" ON "authors" USING btree ("slug");
  CREATE INDEX "authors_avatar_idx" ON "authors" USING btree ("avatar_id");
  CREATE INDEX "authors_legacy_wp_user_id_idx" ON "authors" USING btree ("legacy_wp_user_id");
  CREATE INDEX "authors_updated_at_idx" ON "authors" USING btree ("updated_at");
  CREATE INDEX "authors_created_at_idx" ON "authors" USING btree ("created_at");
  CREATE INDEX "users_sessions_order_idx" ON "users_sessions" USING btree ("_order");
  CREATE INDEX "users_sessions_parent_id_idx" ON "users_sessions" USING btree ("_parent_id");
  CREATE INDEX "users_updated_at_idx" ON "users" USING btree ("updated_at");
  CREATE INDEX "users_created_at_idx" ON "users" USING btree ("created_at");
  CREATE UNIQUE INDEX "users_email_idx" ON "users" USING btree ("email");
  CREATE UNIQUE INDEX "payload_kv_key_idx" ON "payload_kv" USING btree ("key");
  CREATE INDEX "payload_jobs_log_order_idx" ON "payload_jobs_log" USING btree ("_order");
  CREATE INDEX "payload_jobs_log_parent_id_idx" ON "payload_jobs_log" USING btree ("_parent_id");
  CREATE INDEX "payload_jobs_completed_at_idx" ON "payload_jobs" USING btree ("completed_at");
  CREATE INDEX "payload_jobs_total_tried_idx" ON "payload_jobs" USING btree ("total_tried");
  CREATE INDEX "payload_jobs_has_error_idx" ON "payload_jobs" USING btree ("has_error");
  CREATE INDEX "payload_jobs_task_slug_idx" ON "payload_jobs" USING btree ("task_slug");
  CREATE INDEX "payload_jobs_queue_idx" ON "payload_jobs" USING btree ("queue");
  CREATE INDEX "payload_jobs_wait_until_idx" ON "payload_jobs" USING btree ("wait_until");
  CREATE INDEX "payload_jobs_processing_idx" ON "payload_jobs" USING btree ("processing");
  CREATE INDEX "payload_jobs_updated_at_idx" ON "payload_jobs" USING btree ("updated_at");
  CREATE INDEX "payload_jobs_created_at_idx" ON "payload_jobs" USING btree ("created_at");
  CREATE INDEX "payload_locked_documents_global_slug_idx" ON "payload_locked_documents" USING btree ("global_slug");
  CREATE INDEX "payload_locked_documents_updated_at_idx" ON "payload_locked_documents" USING btree ("updated_at");
  CREATE INDEX "payload_locked_documents_created_at_idx" ON "payload_locked_documents" USING btree ("created_at");
  CREATE INDEX "payload_locked_documents_rels_order_idx" ON "payload_locked_documents_rels" USING btree ("order");
  CREATE INDEX "payload_locked_documents_rels_parent_idx" ON "payload_locked_documents_rels" USING btree ("parent_id");
  CREATE INDEX "payload_locked_documents_rels_path_idx" ON "payload_locked_documents_rels" USING btree ("path");
  CREATE INDEX "payload_locked_documents_rels_articles_id_idx" ON "payload_locked_documents_rels" USING btree ("articles_id");
  CREATE INDEX "payload_locked_documents_rels_places_id_idx" ON "payload_locked_documents_rels" USING btree ("places_id");
  CREATE INDEX "payload_locked_documents_rels_events_id_idx" ON "payload_locked_documents_rels" USING btree ("events_id");
  CREATE INDEX "payload_locked_documents_rels_place_mentions_id_idx" ON "payload_locked_documents_rels" USING btree ("place_mentions_id");
  CREATE INDEX "payload_locked_documents_rels_media_id_idx" ON "payload_locked_documents_rels" USING btree ("media_id");
  CREATE INDEX "payload_locked_documents_rels_authors_id_idx" ON "payload_locked_documents_rels" USING btree ("authors_id");
  CREATE INDEX "payload_locked_documents_rels_users_id_idx" ON "payload_locked_documents_rels" USING btree ("users_id");
  CREATE INDEX "payload_preferences_key_idx" ON "payload_preferences" USING btree ("key");
  CREATE INDEX "payload_preferences_updated_at_idx" ON "payload_preferences" USING btree ("updated_at");
  CREATE INDEX "payload_preferences_created_at_idx" ON "payload_preferences" USING btree ("created_at");
  CREATE INDEX "payload_preferences_rels_order_idx" ON "payload_preferences_rels" USING btree ("order");
  CREATE INDEX "payload_preferences_rels_parent_idx" ON "payload_preferences_rels" USING btree ("parent_id");
  CREATE INDEX "payload_preferences_rels_path_idx" ON "payload_preferences_rels" USING btree ("path");
  CREATE INDEX "payload_preferences_rels_users_id_idx" ON "payload_preferences_rels" USING btree ("users_id");
  CREATE INDEX "payload_migrations_updated_at_idx" ON "payload_migrations" USING btree ("updated_at");
  CREATE INDEX "payload_migrations_created_at_idx" ON "payload_migrations" USING btree ("created_at");`)
}

export async function down({ db, payload, req }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
   DROP TABLE "articles" CASCADE;
  DROP TABLE "_articles_v" CASCADE;
  DROP TABLE "places_cuisine" CASCADE;
  DROP TABLE "places_amenities" CASCADE;
  DROP TABLE "places_vibe" CASCADE;
  DROP TABLE "places_hours" CASCADE;
  DROP TABLE "places" CASCADE;
  DROP TABLE "_places_v_version_cuisine" CASCADE;
  DROP TABLE "_places_v_version_amenities" CASCADE;
  DROP TABLE "_places_v_version_vibe" CASCADE;
  DROP TABLE "_places_v_version_hours" CASCADE;
  DROP TABLE "_places_v" CASCADE;
  DROP TABLE "events" CASCADE;
  DROP TABLE "_events_v" CASCADE;
  DROP TABLE "place_mentions" CASCADE;
  DROP TABLE "media" CASCADE;
  DROP TABLE "authors" CASCADE;
  DROP TABLE "users_sessions" CASCADE;
  DROP TABLE "users" CASCADE;
  DROP TABLE "payload_kv" CASCADE;
  DROP TABLE "payload_jobs_log" CASCADE;
  DROP TABLE "payload_jobs" CASCADE;
  DROP TABLE "payload_locked_documents" CASCADE;
  DROP TABLE "payload_locked_documents_rels" CASCADE;
  DROP TABLE "payload_preferences" CASCADE;
  DROP TABLE "payload_preferences_rels" CASCADE;
  DROP TABLE "payload_migrations" CASCADE;
  DROP TYPE "public"."enum_articles_kind";
  DROP TYPE "public"."enum_articles_primary_type";
  DROP TYPE "public"."enum_articles_format";
  DROP TYPE "public"."enum_articles_status";
  DROP TYPE "public"."enum__articles_v_version_kind";
  DROP TYPE "public"."enum__articles_v_version_primary_type";
  DROP TYPE "public"."enum__articles_v_version_format";
  DROP TYPE "public"."enum__articles_v_version_status";
  DROP TYPE "public"."enum_places_cuisine";
  DROP TYPE "public"."enum_places_amenities";
  DROP TYPE "public"."enum_places_vibe";
  DROP TYPE "public"."enum_places_hours_day";
  DROP TYPE "public"."enum_places_area_term";
  DROP TYPE "public"."enum_places_type";
  DROP TYPE "public"."enum_places_subtype";
  DROP TYPE "public"."enum_places_price_band";
  DROP TYPE "public"."enum_places_status";
  DROP TYPE "public"."enum__places_v_version_cuisine";
  DROP TYPE "public"."enum__places_v_version_amenities";
  DROP TYPE "public"."enum__places_v_version_vibe";
  DROP TYPE "public"."enum__places_v_version_hours_day";
  DROP TYPE "public"."enum__places_v_version_area_term";
  DROP TYPE "public"."enum__places_v_version_type";
  DROP TYPE "public"."enum__places_v_version_subtype";
  DROP TYPE "public"."enum__places_v_version_price_band";
  DROP TYPE "public"."enum__places_v_version_status";
  DROP TYPE "public"."enum_events_status";
  DROP TYPE "public"."enum__events_v_version_status";
  DROP TYPE "public"."enum_place_mentions_role";
  DROP TYPE "public"."enum_users_role";
  DROP TYPE "public"."enum_payload_jobs_log_task_slug";
  DROP TYPE "public"."enum_payload_jobs_log_state";
  DROP TYPE "public"."enum_payload_jobs_task_slug";`)
}
