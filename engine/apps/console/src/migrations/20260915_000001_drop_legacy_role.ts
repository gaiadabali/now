import { type MigrateDownArgs, type MigrateUpArgs, sql } from '@payloadcms/db-postgres'

/**
 * The CONTRACT half of the role split. Drops the legacy `role` column.
 *
 * `20260915_000000` deliberately left it in place so that old and new code
 * could both run against the same database during a rollout. This removes it,
 * and **must not run until every process reading `role` has been replaced** —
 * in practice, until the console image carrying the two-dimension collection
 * is actually serving.
 *
 * Running it early does not corrupt anything; it breaks the running console,
 * which starts erroring on a column that no longer exists. Running it late
 * costs nothing but a redundant column. So when in doubt, late.
 *
 * Verifying it is safe to run:
 *
 *     docker exec now-postgres psql -U now -d now_platform -c \\
 *       "SELECT email, editorial_role, commerce_role, role FROM users"
 *
 * If `editorial_role`/`commerce_role` are populated and the deployed console
 * is the new image, this is safe.
 */
export async function up({ db }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
    ALTER TABLE "users" DROP COLUMN IF EXISTS "role";
    DROP TYPE IF EXISTS "public"."enum_users_role";
  `)
}

/**
 * Rebuilds `role` from `commerce_role`.
 *
 * Reconstructed, not restored: the original values are gone, and a user whose
 * commercial access is `none` has no counterpart in the old three-value enum,
 * so they come back as `viewer` — the least-privileged option available.
 * Anyone who had editorial standing and no commercial standing therefore
 * gains a nominal `viewer` role on the way down. That is a consequence of the
 * old model being unable to express them, not of this migration.
 */
export async function down({ db }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
    CREATE TYPE "public"."enum_users_role" AS ENUM('admin', 'partner_manager', 'viewer');

    ALTER TABLE "users" ADD COLUMN "role" "public"."enum_users_role" DEFAULT 'viewer' NOT NULL;

    UPDATE "users"
       SET "role" = CASE WHEN "commerce_role"::text = 'none' THEN 'viewer'::"public"."enum_users_role"
                         ELSE "commerce_role"::text::"public"."enum_users_role" END;
  `)
}
