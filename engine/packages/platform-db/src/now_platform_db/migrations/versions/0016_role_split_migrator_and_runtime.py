"""F7 — split the one Postgres role into a migrator and a runtime role

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-26

Phase 0 (P0.4), plan §5.4 ("Before money lands in this database, two
recorded gaps become blocking: F7... and F6"), PROGRESS.md F7, SURFACES-PLAN.md
§F7. Lands before 0017 (RLS) because RLS policies grant/restrict behaviour
per role, and the roles have to exist first.

## What was true before this migration

`\\du` against the local platform DB showed exactly one role: `now` —
`Superuser, Create role, Create DB, Replication, Bypass RLS`. Every
process that has ever touched `now_platform` — Alembic migrations,
`engine-api`, the web app, `now-loader`, ad hoc `psql` — connects as this
one superuser. A superuser bypasses every grant and every RLS policy that
will ever exist by definition (Postgres: "row security is not applied ...
if the current user has the `BYPASSRLS` attribute" and superusers always
do), so 0017's entire RLS migration would be a no-op against the role the
app has always used. This migration is the prerequisite that makes RLS
mean anything.

## Two roles, not a spectrum of them

- **`now_migrator`** — runs Alembic, owns every object in `engine`, has
  `BYPASSRLS`. It is deliberately still a powerful role: someone has to be
  able to run a migration that touches every row regardless of site, and a
  backoffice/ops script that genuinely needs a cross-site view (the kind of
  thing `now-loader`, `now-db site:create`, or a future "read every city's
  data" report needs) is exactly the audience `BYPASSRLS` describes. What it
  is NOT is `SUPERUSER` — it cannot create other roles, cannot create
  databases, and (per Postgres's own privilege model) is bound by whatever
  grants this migration gives it, same as any other non-superuser role.
- **`now_runtime`** — what the application is meant to connect as. `LOGIN`,
  no `BYPASSRLS`, no `CREATEDB`/`CREATEROLE`, and (0017) no grant on
  `alembic_version`. It cannot run `CREATE TABLE`/`ALTER TABLE`/`DROP TABLE`
  in `engine` at all: `GRANT USAGE ON SCHEMA engine` is given, `CREATE ON
  SCHEMA engine` deliberately is not, and object-level DDL requires schema
  `CREATE` (to make a new object) or table ownership (to alter/drop an
  existing one) — this role holds neither. "runtime role cannot DDL" (this
  ticket's own acceptance line) is therefore not a convention, it is what
  `\\dn+ engine` will show.

## No password is set here, on purpose

`CREATE ROLE ... LOGIN` with no `PASSWORD` clause creates a role that
exists and can be granted to, but cannot authenticate over a password-based
connection until one is set — and setting a real password inside a
migration file means committing it to git history forever. The rollout
checklist (this ticket's Phase 0 doc section) says exactly where the real
password comes from per environment (a deploy secret, `ALTER ROLE ...
PASSWORD` run out of band) and that production is not touched by this PR at
all. Locally, `SET ROLE`/`SET LOCAL ROLE` from a superuser session — which
is how this migration's own pytest suite exercises `now_runtime` — needs no
password; only a real over-the-wire connection as that role does.

## Idempotent against a role that already exists

Postgres has no `CREATE ROLE IF NOT EXISTS`. Wrapped in a `DO` block that
checks `pg_roles` first, so re-running `now-platform-db migrate` against a
database where a previous attempt already created the role (interrupted
mid-migration, or a manually-created role of the same name) does not error
`role "now_migrator" already exists` and abort a later statement in this
same file partway through.

## Ownership is reassigned inside `engine` only, not database-wide

`REASSIGN OWNED BY now TO now_migrator` would be the one-liner, and was
rejected: it reassigns *every* object `now` owns in this database,
including `public.spatial_ref_sys` (created by `CREATE EXTENSION postgis`
in migration 0001, extension-owned, not something this ticket's scope has
any reason to touch) and anything a future `public` Payload instance might
add to this same database (ARCHITECTURE.md §2's "a Payload instance will
own platform public later" — a table this migration cannot know the shape
of yet). Reassigning ownership object-by-object, scoped to `n.nspname =
'engine'`, changes exactly what this migration is about and nothing a
future Payload migration on `public` would need to reason about.

## Default privileges cover the transition period, not just the future

Migrations continue to run as whatever role `NOW_PLATFORM_DATABASE_URL`
resolves to today — `now` locally, `postgres` in this project's own CI
containers (`schema-gate.yml`/`payload-entity-typing-gate.yml` both connect
as `postgres`), something else again wherever this runs next — until a
deliberate, separate cutover ("Do NOT change production" / "keep existing
runtime code working"). **The name of that role cannot be hardcoded**: an
earlier version of this migration wrote `ALTER DEFAULT PRIVILEGES FOR ROLE
now ...` literally, which is exactly the local convenience default this
package's own README documents (`now_platform_db.settings.DEFAULT_USER =
"now"`) — and CI, which has no reason to share that default, failed with
`role "now" does not exist` the first time this ran there. Fixed by reading
`current_user` at migration time and using it as the role name, via a `DO`
block and `format('%I', ...)`, so this migration sets `ALTER DEFAULT
PRIVILEGES` for *both* `now_migrator` (the role migrations should run as,
going forward) and *whichever role is actually connected running this
migration right now* (skipped if that happens to already be `now_migrator`,
to avoid a redundant no-op statement) — a table created by either role in
`engine` from this point on is automatically readable/writable by
`now_runtime` at the standard CRUD level, without every future migration
needing its own grant statement. The append-only/no-delete narrowing 0017
applies to specific tables (ledgers, financial records) is a *deliberate
exception* to that default and has to be restated by hand for any such
table added later — documented in this package's README under "Notes for
later waves".

The same fix applies to the downgrade's ownership reversal: it restores
ownership to `current_user` (whoever is running the downgrade), not a
hardcoded name — the closest generic approximation of "put it back the way
it was" available without this migration recording who owned what before
it ran. If the downgrade is ever run as `now_migrator` itself (e.g. after
a full cutover), ownership simply stays with `now_migrator` — a reasonable
no-op in that case, not a failure.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'now_migrator') THEN
                CREATE ROLE now_migrator
                    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION BYPASSRLS;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'now_runtime') THEN
                CREATE ROLE now_runtime
                    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
            END IF;
        END
        $$
        """
    )

    op.execute("GRANT USAGE, CREATE ON SCHEMA engine TO now_migrator")
    op.execute("GRANT USAGE ON SCHEMA engine TO now_runtime")

    # Reassign ownership of every existing engine-schema table, partitioned
    # table, VIEW, materialized view, and function to now_migrator. Scoped
    # to the `engine` namespace only — see docstring for why a blanket
    # `REASSIGN OWNED BY` is wrong here.
    #
    # Views ('v') and materialized views ('m') are included, not just
    # tables ('r') and partitioned tables ('p') — found in review: a plain
    # view (0003's `engine.partnerships_active`) evaluates row-level
    # security against its OWNER, not its caller, unless the view has
    # `security_invoker = true` (0017 sets that too, on the one view that
    # exists today). Leaving a view's ownership un-reassigned here would
    # have left it silently owned by whatever role ran 0003 — today's
    # ambient superuser, which bypasses RLS regardless of the view, so the
    # gap is latent rather than exploitable yet, but it would become a live
    # cross-site leak the moment any grant let `now_runtime` query the view
    # without also getting this reassignment. `ALTER TABLE` cannot change a
    # view's or materialized view's owner (Postgres: "... is not a table"),
    # so the loop branches on `relkind` and issues the command each kind
    # actually accepts.
    op.execute(
        """
        DO $$
        DECLARE
            r record;
        BEGIN
            FOR r IN
                SELECT c.relname, c.relkind
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'engine' AND c.relkind IN ('r', 'p', 'v', 'm')
            LOOP
                IF r.relkind = 'v' THEN
                    EXECUTE format('ALTER VIEW engine.%I OWNER TO now_migrator', r.relname);
                ELSIF r.relkind = 'm' THEN
                    EXECUTE format('ALTER MATERIALIZED VIEW engine.%I OWNER TO now_migrator', r.relname);
                ELSE
                    EXECUTE format('ALTER TABLE engine.%I OWNER TO now_migrator', r.relname);
                END IF;
            END LOOP;

            FOR r IN
                SELECT p.oid::regprocedure::text AS signature
                  FROM pg_proc p
                  JOIN pg_namespace n ON n.oid = p.pronamespace
                 WHERE n.nspname = 'engine'
            LOOP
                EXECUTE format('ALTER FUNCTION %s OWNER TO now_migrator', r.signature);
            END LOOP;
        END
        $$
        """
    )
    op.execute("ALTER SCHEMA engine OWNER TO now_migrator")

    # Transition-period default privileges — see docstring. Every table
    # created from here on by either role gets the standard CRUD grant for
    # now_runtime; ledgers/financial tables narrow this explicitly (0017),
    # and any *new* ledger-shaped table added after this migration must
    # repeat that narrowing by hand (README note added alongside this file).
    op.execute(
        """
        ALTER DEFAULT PRIVILEGES FOR ROLE now_migrator IN SCHEMA engine
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO now_runtime
        """
    )
    # Whatever role is actually connected and running this migration right
    # now — `now` locally, `postgres` in CI, potentially something else
    # elsewhere — NOT a hardcoded name (see docstring: this exact line used
    # to say `FOR ROLE now` and broke CI with "role \"now\" does not exist").
    op.execute(
        """
        DO $$
        DECLARE
            runner text := current_user;
        BEGIN
            IF runner <> 'now_migrator' THEN
                EXECUTE format(
                    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA engine '
                    'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO now_runtime',
                    runner
                );
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    # Roles are cluster-level and may be referenced by grants this
    # migration did not create (a manually-provisioned deploy secret, a
    # connection already open as one of them) — dropping them here would be
    # reaching outside this migration's own blast radius. The downgrade
    # undoes what this migration is actually responsible for: the ownership
    # transfer and the schema-level grants, restoring current_user (whoever
    # runs this downgrade) as owner and sole schema-privileged role. It
    # deliberately does NOT `DROP ROLE`; an operator who wants the roles
    # gone entirely does that by hand, after confirming nothing still
    # depends on them.
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE now_migrator IN SCHEMA engine "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM now_runtime"
    )
    # Mirrors the dynamic grant in upgrade() — whatever role is running the
    # downgrade, not a hardcoded name.
    op.execute(
        """
        DO $$
        DECLARE
            runner text := current_user;
        BEGIN
            IF runner <> 'now_migrator' THEN
                EXECUTE format(
                    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA engine '
                    'REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM now_runtime',
                    runner
                );
            END IF;
        END
        $$
        """
    )
    # Ownership reverts to whoever is running the downgrade (current_user),
    # not a hardcoded name — see docstring for why "put it back exactly as
    # it was" isn't knowable in general, and why this is the closest
    # sensible default.
    op.execute(
        """
        DO $$
        DECLARE
            r record;
            runner text := current_user;
        BEGIN
            FOR r IN
                SELECT c.relname, c.relkind
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'engine' AND c.relkind IN ('r', 'p', 'v', 'm')
            LOOP
                IF r.relkind = 'v' THEN
                    EXECUTE format('ALTER VIEW engine.%I OWNER TO %I', r.relname, runner);
                ELSIF r.relkind = 'm' THEN
                    EXECUTE format('ALTER MATERIALIZED VIEW engine.%I OWNER TO %I', r.relname, runner);
                ELSE
                    EXECUTE format('ALTER TABLE engine.%I OWNER TO %I', r.relname, runner);
                END IF;
            END LOOP;

            FOR r IN
                SELECT p.oid::regprocedure::text AS signature
                  FROM pg_proc p
                  JOIN pg_namespace n ON n.oid = p.pronamespace
                 WHERE n.nspname = 'engine'
            LOOP
                EXECUTE format('ALTER FUNCTION %s OWNER TO %I', r.signature, runner);
            END LOOP;

            EXECUTE format('ALTER SCHEMA engine OWNER TO %I', runner);
        END
        $$
        """
    )
    op.execute("REVOKE USAGE, CREATE ON SCHEMA engine FROM now_migrator")
    op.execute("REVOKE USAGE ON SCHEMA engine FROM now_runtime")
