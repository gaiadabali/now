"""print edition commerce — plans, orders, subscriptions, shipments, payment ledger

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-26

Phase 0 (P0.1), plan §5.4, folded forward from Phase 5 into Phase 0 per this
ticket's brief. Independent of 0012/0013 — no FK to `offers` or
`destinations` — so it could in principle land anywhere after 0001, but sits
here to keep "money" together as one reviewable block (0012/0014 — offers,
print) ahead of the role/RLS migrations (0016/0017) that lock both down.

## `gateway` is the provider column the brief asks for

§11a answer 4 is explicit and the reason this table exists ahead of a real
payment integration: "Build behind a provider interface and ship a
simulated gateway first... so Midtrans or Xendit is a later drop-in."
`gateway` is that column — `CHECK (gateway IN ('simulated', 'midtrans',
'xendit'))`, nullable (an order in `pending_payment` before a hosted
session has been created has no gateway yet), so a `simulated` order today
and a `midtrans` order tomorrow are rows in the same table distinguished by
one value, never by a schema change. `gateway_order_ref` is the gateway's
own reference (its invoice/order id) and is `UNIQUE` — the idempotency key
a webhook handler needs regardless of which provider sends it.
`payment_events.gateway` carries the same vocabulary for the same reason:
one webhook-ledger shape for every provider that will ever exist behind
this interface.

## No guest checkout — §11a answer 5, enforced here, not just in the app

"An account is required to buy print. No guest checkout." `print_orders.
identity_id` is therefore `NOT NULL` (the plan's own sketch had it nullable
for a guest-checkout design the owner rejected) — the schema does not leave
the door open for a code path that forgets to check for a session. It is
`ON DELETE SET NULL` even so: an order is a financial record with retention
obligations distinct from the account rules (P2.9, plan roadmap: "deleting
an account leaves zero rows in the new tables except orders (retained per
finance, anonymised)"), so a deleted reader's past orders survive,
un-attributed, exactly as `itineraries.user_id` already does (0008).
`email`/`email_norm` stay on the row regardless, matching that "anonymised,
not erased" plan for the delivery/finance record — export/delete (P2.9)
scrubs identity, not the fact that an order existed. Note this is
deliberately NOT what 0007 chose for `identities` itself (hard delete of
credentials on account deletion) — a person's login and a finished sale are
different kinds of record with different retention reasons, and treating
them alike would either keep credentials too long or lose finance history
too early.

## Nothing here is ever `DELETE`d by the runtime role

Anticipates P0.4 (0017's grants): every table in this migration is a
financial record. `print_orders`/`print_order_items`/`print_subscriptions`/
`shipments` are cancelled or superseded by an `UPDATE` to `status`, never a
row deletion — `payment_events` is a pure append-only webhook ledger, same
posture as `ad_events` and `offer_events`. This migration does not grant
anything itself (0016 creates the roles, 0017 does the granting), but the
schema is shaped for that policy from the start: no table here has a
lifecycle that legitimately needs `DELETE`.

## `payment_events` is idempotent on `(gateway, event_ref)`, not on `id`

A webhook can be redelivered — every gateway's own documentation says so —
and the correct response to a replay is a no-op, not a second row. The
`UNIQUE (gateway, event_ref)` constraint is what makes
`INSERT ... ON CONFLICT (gateway, event_ref) DO NOTHING` the entire
idempotency mechanism at the database layer, matching P5.3's acceptance
line ("`payment_events` rejects a duplicate `(gateway, event_ref)`") word
for word. `signature_ok boolean NOT NULL` records whether the webhook's
signature verified even when it did not — a forged webhook is logged, not
silently dropped, so the daily reconciliation has something to look at.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[Sequence[str], str, None] = None
depends_on: Union[Sequence[str], str, None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE engine.print_plans (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            site_id        uuid NOT NULL REFERENCES engine.sites(id),
            kind           text NOT NULL CHECK (kind IN ('single_issue', 'term')),
            term_issues    integer,
            price_idr      integer NOT NULL,
            delivery_zone  text NOT NULL,
            active         boolean NOT NULL DEFAULT true,
            created_at     timestamptz NOT NULL DEFAULT now(),
            updated_at     timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT print_plans_term_issues_ck
                CHECK ((kind = 'term' AND term_issues IS NOT NULL AND term_issues > 0)
                    OR (kind = 'single_issue' AND term_issues IS NULL))
        )
        """
    )
    op.execute("CREATE INDEX ix_print_plans_site_active ON engine.print_plans (site_id) WHERE active")

    op.execute(
        """
        CREATE TABLE engine.print_orders (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            -- §11a answer 5: no guest checkout. An order always has a reader.
            identity_id       uuid NOT NULL REFERENCES engine.identities(id) ON DELETE SET NULL,
            site_id           uuid NOT NULL REFERENCES engine.sites(id),
            email             text NOT NULL,
            email_norm        text NOT NULL,
            status            text NOT NULL
                              CHECK (status IN
                                  ('pending_payment', 'paid', 'fulfilling', 'shipped',
                                   'cancelled', 'refunded', 'expired')),
            subtotal_idr      integer NOT NULL,
            shipping_idr      integer NOT NULL,
            total_idr         integer NOT NULL,
            currency          text NOT NULL DEFAULT 'IDR',
            delivery          jsonb NOT NULL,
            gateway           text CHECK (gateway IS NULL OR gateway IN ('simulated', 'midtrans', 'xendit')),
            gateway_order_ref text UNIQUE,
            paid_at           timestamptz,
            expires_at        timestamptz,
            created_at        timestamptz NOT NULL DEFAULT now(),
            updated_at        timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_print_orders_identity ON engine.print_orders (identity_id)")
    op.execute("CREATE INDEX ix_print_orders_site ON engine.print_orders (site_id)")
    # The 24h expiry job (§5.5 step 2): pending orders past their deadline.
    op.execute(
        """
        CREATE INDEX ix_print_orders_pending_expiry
            ON engine.print_orders (expires_at)
            WHERE status = 'pending_payment'
        """
    )

    op.execute(
        """
        CREATE TABLE engine.print_order_items (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            order_id         uuid NOT NULL REFERENCES engine.print_orders(id) ON DELETE CASCADE,
            plan_id          uuid NOT NULL REFERENCES engine.print_plans(id),
            edition_site_id  uuid REFERENCES engine.sites(id),
            edition_id       text,
            qty              integer NOT NULL CHECK (qty > 0),
            unit_price_idr   integer NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_print_order_items_order ON engine.print_order_items (order_id)")

    op.execute(
        """
        CREATE TABLE engine.print_subscriptions (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            identity_id       uuid NOT NULL REFERENCES engine.identities(id) ON DELETE RESTRICT,
            site_id           uuid NOT NULL REFERENCES engine.sites(id),
            plan_id           uuid NOT NULL REFERENCES engine.print_plans(id),
            order_id          uuid REFERENCES engine.print_orders(id),
            status            text NOT NULL
                              CHECK (status IN ('active', 'expiring', 'expired', 'cancelled')),
            issues_total      integer NOT NULL,
            issues_sent       integer NOT NULL DEFAULT 0,
            starts_with_issue date NOT NULL,
            ends_after_issue  date NOT NULL,
            delivery          jsonb NOT NULL,
            auto_renew        boolean NOT NULL DEFAULT false,
            payment_token_ref text,
            created_at        timestamptz NOT NULL DEFAULT now(),
            updated_at        timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_print_subscriptions_identity ON engine.print_subscriptions (identity_id)")
    op.execute("CREATE INDEX ix_print_subscriptions_site ON engine.print_subscriptions (site_id)")
    # The 30-day renewal reminder job (P5.6).
    op.execute(
        """
        CREATE INDEX ix_print_subscriptions_active_end
            ON engine.print_subscriptions (ends_after_issue)
            WHERE status IN ('active', 'expiring')
        """
    )

    op.execute(
        """
        CREATE TABLE engine.shipments (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            order_id         uuid REFERENCES engine.print_orders(id),
            subscription_id  uuid REFERENCES engine.print_subscriptions(id),
            edition_site_id  uuid NOT NULL REFERENCES engine.sites(id),
            edition_id       text NOT NULL,
            courier          text,
            tracking_no      text,
            shipped_at       timestamptz,
            created_at       timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT shipments_order_or_subscription_ck
                CHECK (num_nonnulls(order_id, subscription_id) = 1)
        )
        """
    )
    op.execute("CREATE INDEX ix_shipments_order ON engine.shipments (order_id) WHERE order_id IS NOT NULL")
    op.execute(
        """
        CREATE INDEX ix_shipments_subscription
            ON engine.shipments (subscription_id)
            WHERE subscription_id IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE engine.payment_events (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            gateway       text NOT NULL CHECK (gateway IN ('simulated', 'midtrans', 'xendit')),
            event_ref     text NOT NULL,
            order_id      uuid REFERENCES engine.print_orders(id),
            kind          text NOT NULL,
            signature_ok  boolean NOT NULL,
            payload       jsonb NOT NULL,
            received_at   timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_payment_events_gateway_ref UNIQUE (gateway, event_ref)
        )
        """
    )
    op.execute("CREATE INDEX ix_payment_events_order ON engine.payment_events (order_id) WHERE order_id IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS engine.payment_events")
    op.execute("DROP TABLE IF EXISTS engine.shipments")
    op.execute("DROP TABLE IF EXISTS engine.print_subscriptions")
    op.execute("DROP TABLE IF EXISTS engine.print_order_items")
    op.execute("DROP TABLE IF EXISTS engine.print_orders")
    op.execute("DROP TABLE IF EXISTS engine.print_plans")
