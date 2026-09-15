import { type MigrateDownArgs, type MigrateUpArgs, sql } from '@payloadcms/db-postgres'

/**
 * Splits the single `role` column into two independent dimensions.
 *
 * The CMS and this console arrived with disjoint vocabularies —
 * `admin|editor|author` for publishing, `admin|partner_manager|viewer` for
 * commercial data. docs/ADMIN-CONSOLIDATION.md merges the two surfaces behind
 * one sign-in, so a single account has to carry both, and one column cannot:
 * "an editor who may also read partner terms" and "a partner manager who may
 * not publish" are both real, and collapsing them means either over-granting
 * or an enum that grows multiplicatively.
 *
 * **Data mapping, and why it is not symmetrical:**
 *
 *   commerce_role  <- role, exactly. This column IS the old one, renamed in
 *                     meaning as well as name; nobody gains or loses
 *                     commercial access here.
 *   editorial_role <- 'admin' where role = 'admin', otherwise 'none'.
 *
 * That second line is the one judgement call. `none` everywhere would be the
 * purer default, but it would lock the bootstrap admin — currently the only
 * account — out of the CMS the moment the surfaces merge, with no one able to
 * grant it back. Existing admins keep equivalent standing; everyone else
 * starts with no editorial access and is granted it deliberately.
 *
 * Written by hand rather than generated: `payload migrate:create` prompts
 * interactively about whether each enum is created or renamed, which cannot
 * be answered in CI or over a non-interactive shell.
 */
export async function up({ db }: MigrateUpArgs): Promise<void> {
  await db.execute(sql`
    CREATE TYPE "public"."enum_users_editorial_role" AS ENUM('admin', 'editor', 'author', 'none');
    CREATE TYPE "public"."enum_users_commerce_role" AS ENUM('admin', 'partner_manager', 'viewer', 'none');

    ALTER TABLE "users" ADD COLUMN "editorial_role" "public"."enum_users_editorial_role" DEFAULT 'none' NOT NULL;
    ALTER TABLE "users" ADD COLUMN "commerce_role" "public"."enum_users_commerce_role" DEFAULT 'none' NOT NULL;

    UPDATE "users"
       SET "commerce_role"  = "role"::text::"public"."enum_users_commerce_role",
           "editorial_role" = CASE WHEN "role"::text = 'admin' THEN 'admin'::"public"."enum_users_editorial_role"
                                   ELSE 'none'::"public"."enum_users_editorial_role" END;

    ALTER TABLE "users" DROP COLUMN "role";
    DROP TYPE "public"."enum_users_role";
  `)
}

/**
 * Collapses back to a single column, keeping the commercial dimension.
 *
 * Editorial standing is **lost** on the way down — there is no column to put
 * it in. That is inherent to the reversal, not an oversight: anyone granted
 * editorial access after this migration ran will need it re-granted if it is
 * ever rolled back.
 */
export async function down({ db }: MigrateDownArgs): Promise<void> {
  await db.execute(sql`
    CREATE TYPE "public"."enum_users_role" AS ENUM('admin', 'partner_manager', 'viewer');

    ALTER TABLE "users" ADD COLUMN "role" "public"."enum_users_role" DEFAULT 'viewer' NOT NULL;

    UPDATE "users"
       SET "role" = CASE WHEN "commerce_role"::text = 'none' THEN 'viewer'::"public"."enum_users_role"
                         ELSE "commerce_role"::text::"public"."enum_users_role" END;

    ALTER TABLE "users" DROP COLUMN "editorial_role";
    ALTER TABLE "users" DROP COLUMN "commerce_role";
    DROP TYPE "public"."enum_users_editorial_role";
    DROP TYPE "public"."enum_users_commerce_role";
  `)
}
