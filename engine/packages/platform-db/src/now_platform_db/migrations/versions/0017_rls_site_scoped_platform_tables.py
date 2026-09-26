"""F6 — row-level security on site-scoped platform tables, and the runtime grants

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-26

Phase 0 (P0.4), plan §5.4 / SURFACES-PLAN.md F6, PROGRESS.md F6. Depends on
0016 (the `now_migrator`/`now_runtime` roles): a policy that only restricts
a superuser restricts nothing, since a superuser bypasses row security by
definition (`now`, today's only role, is one — see 0016's docstring).
Everything in this migration is inert against the connection the app uses
today and becomes load-bearing only once that connection is deliberately
recabled onto `now_runtime` (this ticket's rollout checklist says exactly
when and how) — "keep existing runtime code working" / "do NOT change
production" are both true of every statement below.

## The session-variable convention this migration establishes

There is no tenant column on the *connection*, so a policy needs something
in the session to compare `site_id` against. This migration picks the
standard Postgres multi-tenant idiom — a custom GUC, set per request/
transaction by the application:

    SET LOCAL app.site_id = '<the site uuid the current request is for>';

and defines `engine.current_site_id()` as the one place every policy reads
it from:

```sql
CREATE FUNCTION engine.current_site_id() RETURNS uuid AS $$
  read current_setting('app.site_id', true); NULL if unset or unparseable
$$;
```

**Fails closed, not loud.** An unset or garbage `app.site_id` returns SQL
NULL, and `site_id = NULL` is never true — so a request that forgets to set
the session variable sees zero rows in every RLS-protected table rather
than erroring out (which could be caught and worked around) or, far worse,
seeing every site's rows (which a naive `current_setting(...)::uuid` with
no fallback would do by raising an exception that some `try/except`
somewhere quietly swallows). The acceptance line this is built for
("a `partner_manager` session for Bali cannot read a Jakarta offer through
any console query") includes the buggy console query that forgot to set
the site at all — that is exactly the case FORCE RLS + fail-closed exists
for, per this senior-db seat's own mandate: RLS is the thing that makes the
unintended query *impossible*, not merely documented against.

**Cross-site admin views fan out at the application layer, not through a
bypass role.** A commerce `admin` who legitimately needs to see every
site's offers does so exactly the way ARCHITECTURE.md §2 already describes
cross-city reads working ("fan out at the application layer and merge") —
loop the known sites, `SET LOCAL app.site_id` to each in turn, merge in
Python/TypeScript. No table in this migration grants `now_runtime` a way to
see two sites in one query; that is not an oversight, it is the whole
point of §5.4's "one policy mistake leaks or blocks a city" risk the
roadmap flags this ticket against.

## Which tables get FORCE RLS, and why the boundary is drawn here

This ticket's brief: "partnerships, campaigns, placements, and the new
offers/print tables." Read literally and applied to every table added in
this Phase 0 set that is either directly `site_id`-scoped or reachable from
one hop of a foreign key to a directly-scoped table:

- **Direct `site_id` column** (`USING (site_id = engine.current_site_id())`):
  `partnerships`, `campaigns`, `offers`, `offer_places`, `print_plans`,
  `print_orders`, `print_subscriptions`.
- **One join away** (no `site_id` column of its own — the FK target
  carries it): `placements` (via `campaign_id` → `campaigns.site_id`),
  `voucher_claims` / `offer_events` / `offer_audit` (via `offer_id` →
  `offers.site_id`), `print_order_items` (via `order_id` →
  `print_orders.site_id`), `shipments` (via `order_id` OR
  `subscription_id` — a shipment always has exactly one of the two,
  0014's `shipments_order_or_subscription_ck`), `payment_events` (via
  `order_id` → `print_orders.site_id`; **nullable** — a webhook event that
  arrived with no matching order has no site to attribute and is therefore
  invisible to every site-scoped session, visible only to `now_migrator`'s
  reconciliation queries, which is the correct default for an orphan
  record rather than guessing which site it belongs to).

**Deliberately NOT touched by this migration**, flagged here rather than
silently left out: `ad_events` and `partnership_audit` are exactly as
site-scoped (via `campaign_id`/`partnership_id`) as the tables above, and
are not covered because the brief's explicit list does not name them and
adding policies to tables outside the stated scope is exactly the kind of
unreviewed blast-radius expansion this ticket's own risk framing warns
against. They are the natural next step once this pattern has run in
production for a cycle — tracked in this package's README rather than
silently forgotten. `itineraries`/`destinations`/`reading_progress`/
`saved_items`/`newsletter_subscribers` are reader-owned, not
commercially/tenant-sensitive in the way F6 was raised about, and are
scoped by `identity_id` (a reader's own session already can only construct
queries for themselves at the application layer); `partner_users` gets its
own scoping model in P8.1 (0015's docstring) once the portal's session
design exists.

## Grants: the "runtime role cannot write audit/ledger history it
   shouldn't" half of this ticket's acceptance line

Separate from RLS (which restricts *which rows*), `now_runtime`'s
table-level grants restrict *which operations* — this is what makes an
append-only ledger append-only even from a row it is allowed to see:

- `ad_events`, `partnership_audit`, `offer_events`, `offer_audit`,
  `payment_events` — `SELECT, INSERT` only. No `UPDATE`, no `DELETE`, ever,
  for `now_runtime`. A forged-webhook investigation or a billing dispute
  needs these rows to be exactly what was written, not editable.
- `offers`, `print_plans`, `print_orders`, `print_order_items`,
  `print_subscriptions`, `shipments`, `voucher_claims` — `SELECT, INSERT,
  UPDATE`, no `DELETE`. Every one of these is superseded by a status change
  (`paused`/`ended`/`cancelled`/`refunded`/`revoked`/`expired`), never
  erased — matching the plan's own retention line for orders (P2.9:
  "retained per finance, anonymised") generalised to every commerce record
  in this set.
- `sites` — `SELECT, UPDATE` only. Provisioning a new site
  (`now-db site:create`, ARCHITECTURE.md §2) is an ops/CLI action; toggling
  `enabled_modules`/`status` from `/team-editor/platform/sites` (P0.3) is
  the one write the running application legitimately makes to this table.
- `terms`, `facets` — `SELECT` only. Taxonomy is seeded and edited through
  the migrator/seed path (`packages/taxonomy`), not written by request-time
  application code today.
- `alembic_version` — no grant at all. Migration bookkeeping is
  `now_migrator`'s alone.
- Everything else added in this Phase 0 set, and every pre-existing
  ordinary reader/commerce table, gets the standard `SELECT, INSERT,
  UPDATE, DELETE`.

## Verification performed

`engine/packages/platform-db/tests/test_rls_site_isolation.py` (added in
this same commit) proves every claim above against a real Postgres
connection: `now_runtime` reading `engine.partnerships` with `app.site_id`
set to a Bali fixture site sees only that site's row, sees zero rows with
no `app.site_id` set at all, cannot `INSERT` a Jakarta-site row while
`app.site_id` is set to Bali, cannot `UPDATE`/`DELETE` `engine.ad_events` or
`engine.payment_events` (permission denied, not an empty result — the grant
model, not RLS, is what is being proven there), and cannot execute
`CREATE TABLE engine.sabotage (id int)` at all. `now_migrator`
(BYPASSRLS) sees every site's rows in the same tables regardless of
`app.site_id`. See that file for the actual assertions and their output.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None

# (table, USING/WITH CHECK boolean expression)
_DIRECT_SITE_TABLES: tuple[str, ...] = (
    "partnerships",
    "campaigns",
    "offers",
    "offer_places",
    "print_plans",
    "print_orders",
    "print_subscriptions",
)

_JOINED_POLICIES: dict[str, str] = {
    "placements": (
        "campaign_id IN (SELECT id FROM engine.campaigns WHERE site_id = engine.current_site_id())"
    ),
    "voucher_claims": (
        "offer_id IN (SELECT id FROM engine.offers WHERE site_id = engine.current_site_id())"
    ),
    "offer_events": (
        "offer_id IN (SELECT id FROM engine.offers WHERE site_id = engine.current_site_id())"
    ),
    "offer_audit": (
        "offer_id IN (SELECT id FROM engine.offers WHERE site_id = engine.current_site_id())"
    ),
    "print_order_items": (
        "order_id IN (SELECT id FROM engine.print_orders WHERE site_id = engine.current_site_id())"
    ),
    "shipments": (
        "(order_id IS NOT NULL AND order_id IN "
        "   (SELECT id FROM engine.print_orders WHERE site_id = engine.current_site_id()))"
        " OR "
        "(subscription_id IS NOT NULL AND subscription_id IN "
        "   (SELECT id FROM engine.print_subscriptions WHERE site_id = engine.current_site_id()))"
    ),
    "payment_events": (
        "order_id IS NOT NULL AND order_id IN "
        "(SELECT id FROM engine.print_orders WHERE site_id = engine.current_site_id())"
    ),
}


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION engine.current_site_id() RETURNS uuid
        LANGUAGE plpgsql STABLE AS $$
        DECLARE
            raw text := current_setting('app.site_id', true);
        BEGIN
            IF raw IS NULL OR raw = '' THEN
                RETURN NULL;
            END IF;
            RETURN raw::uuid;
        EXCEPTION WHEN invalid_text_representation THEN
            -- Fail closed: a garbage session variable must mean "no site
            -- matches", never an error the app can swallow and never every
            -- row via a NULL-defeats-the-filter mistake.
            RETURN NULL;
        END;
        $$
        """
    )

    for table in _DIRECT_SITE_TABLES:
        op.execute(f"ALTER TABLE engine.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE engine.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_site_isolation ON engine.{table}
                FOR ALL
                USING (site_id = engine.current_site_id())
                WITH CHECK (site_id = engine.current_site_id())
            """
        )

    for table, condition in _JOINED_POLICIES.items():
        op.execute(f"ALTER TABLE engine.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE engine.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_site_isolation ON engine.{table}
                FOR ALL
                USING ({condition})
                WITH CHECK ({condition})
            """
        )

    op.execute("GRANT EXECUTE ON FUNCTION engine.current_site_id() TO now_runtime")

    # Defensive baseline: no ambient PUBLIC access to anything in engine.
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA engine FROM PUBLIC")

    # Migration bookkeeping — now_migrator only.
    op.execute("REVOKE ALL ON engine.alembic_version FROM now_runtime")

    # `engine.partnerships_active` (0003) — a plain view over `partnerships`,
    # which carries RLS as of this migration. Found in review: by default a
    # view's row-security (and every other permission check inside its
    # query) is evaluated against the VIEW'S OWNER, not the querying role —
    # `security_invoker = true` (Postgres 15+) is what makes it evaluate
    # against whoever is actually running the query instead. Without this,
    # 0016's ownership reassignment (which now includes views) would still
    # leave the view owned by `now_migrator` — a role with `BYPASSRLS` — so
    # *any* grant of `SELECT` on this view to `now_runtime` would bypass
    # every site-isolation policy on the underlying table entirely, through
    # a path this migration's own table-level policies never touch. Setting
    # `security_invoker` first, then granting, closes that before it opens:
    # the console will need this view (it is exactly the "what's live right
    # now, with no cron to go stale" read a partnerships list screen wants),
    # so the grant is added now rather than left as a footgun for whichever
    # ticket adds that screen.
    op.execute("ALTER VIEW engine.partnerships_active SET (security_invoker = true)")
    op.execute("GRANT SELECT ON engine.partnerships_active TO now_runtime")

    # Read-mostly configuration.
    op.execute("GRANT SELECT, UPDATE ON engine.sites TO now_runtime")
    op.execute("GRANT SELECT ON engine.terms, engine.facets TO now_runtime")

    # Append-only ledgers/audit — SELECT + INSERT only, never UPDATE/DELETE.
    op.execute(
        """
        GRANT SELECT, INSERT ON
            engine.ad_events,
            engine.partnership_audit,
            engine.offer_events,
            engine.offer_audit,
            engine.payment_events
        TO now_runtime
        """
    )

    # Durable commerce records — superseded by a status UPDATE, never DELETEd.
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE ON
            engine.offers,
            engine.print_plans,
            engine.print_orders,
            engine.print_order_items,
            engine.print_subscriptions,
            engine.shipments,
            engine.voucher_claims
        TO now_runtime
        """
    )

    # Ordinary reader/commerce/config tables — standard CRUD.
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE ON
            engine.orgs,
            engine.partnerships,
            engine.campaigns,
            engine.placements,
            engine.offer_places,
            engine.itineraries,
            engine.itinerary_days,
            engine.itinerary_stops,
            engine.itinerary_items,
            engine.destinations,
            engine.reading_progress,
            engine.newsletter_subscribers,
            engine.identities,
            engine.identity_tokens,
            engine.saved_items,
            engine.user_profiles,
            engine.syndications,
            engine.partner_users,
            engine.partner_user_tokens
        TO now_runtime
        """
    )


def downgrade() -> None:
    for table in list(_JOINED_POLICIES) + list(_DIRECT_SITE_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_site_isolation ON engine.{table}")
        op.execute(f"ALTER TABLE engine.{table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE engine.{table} DISABLE ROW LEVEL SECURITY")

    # `REVOKE ALL ON ALL TABLES IN SCHEMA engine` already covers the view
    # (Postgres's "ALL TABLES IN SCHEMA" includes views, just not
    # sequences) — only the security_invoker setting needs its own reset.
    op.execute("ALTER VIEW engine.partnerships_active SET (security_invoker = false)")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA engine FROM now_runtime")
    op.execute("REVOKE EXECUTE ON FUNCTION engine.current_site_id() FROM now_runtime")
    op.execute("DROP FUNCTION IF EXISTS engine.current_site_id()")
