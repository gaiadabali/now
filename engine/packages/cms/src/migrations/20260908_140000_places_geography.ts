import type { MigrateDownArgs, MigrateUpArgs } from '@payloadcms/db-postgres'
import { sql } from '@payloadcms/db-postgres'

/**
 * Hand-authored migration (not generated from a field diff) — see
 * `src/collections/Places.ts` and README.md "Places.geo: a real
 * ARCHITECTURE.md/Payload friction point" for the full rationale.
 *
 * ARCHITECTURE.md §5 types `places.geo` as `geography(Point,4326)` so
 * engine-api can run PostGIS `ST_DWithin` radius queries (§7 Row 2, §15).
 * Payload has no `geography` field type — its own `point` field maps to
 * Postgres's native `point`, which `ST_DWithin`/`geography` functions
 * cannot consume directly. Editors edit plain `lat`/`lng` numbers (see the
 * Places collection); this migration adds the real `geography` column
 * Postgres/PostGIS expects and a trigger that keeps it derived from
 * lat/lng on every insert/update, so the two never drift.
 *
 * This is still 100% "Payload owns public, Alembic owns engine" —
 * Alembic is not involved anywhere in this file, and this is Payload's
 * own migration runner (`payload migrate`) shaping a table Payload itself
 * created in the previous migration. It is exactly analogous to what
 * `now_db`'s Alembic migrations do inside `engine`, just on the other
 * side of the schema boundary.
 */
export async function up({ db }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
    ALTER TABLE "places" ADD COLUMN IF NOT EXISTS "geo" geography(Point, 4326);

    CREATE OR REPLACE FUNCTION now_places_sync_geo() RETURNS trigger AS $$
    BEGIN
      IF NEW.lat IS NOT NULL AND NEW.lng IS NOT NULL THEN
        NEW.geo := ST_SetSRID(ST_MakePoint(NEW.lng::double precision, NEW.lat::double precision), 4326)::geography;
      ELSE
        NEW.geo := NULL;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS trg_places_sync_geo ON "places";
    CREATE TRIGGER trg_places_sync_geo
      BEFORE INSERT OR UPDATE OF lat, lng ON "places"
      FOR EACH ROW EXECUTE FUNCTION now_places_sync_geo();

    -- Backfill any rows written before this migration ran.
    UPDATE "places" SET lat = lat WHERE lat IS NOT NULL AND lng IS NOT NULL;

    CREATE INDEX IF NOT EXISTS ix_places_geo ON "places" USING gist ("geo");
  `)
}

export async function down({ db }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
    DROP INDEX IF EXISTS ix_places_geo;
    DROP TRIGGER IF EXISTS trg_places_sync_geo ON "places";
    DROP FUNCTION IF EXISTS now_places_sync_geo();
    ALTER TABLE "places" DROP COLUMN IF EXISTS "geo";
  `)
}
