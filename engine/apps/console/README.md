# `@now-engine/console` — schema owner for `now_platform.public`

**This is not an application.** It serves no pages, builds no image, and runs
in no container. It is a Payload config whose only job is to own the schema of
`now_platform.public` and to keep the migration history for it.

## Why it still exists

The partner console was absorbed into the reader app at
`/team-editor/commerce` ([docs/ADMIN-CONSOLIDATION.md](../../../docs/ADMIN-CONSOLIDATION.md)
Phases 3–4). Its pages moved, its admin UI was retired, its container and
hostname are gone.

What did **not** move is schema ownership. `public.users` is the staff
identity store that every admin sign-in authenticates against, and
`src/migrations/` is the only record of how that table came to be — including
the two-dimension role split that replaced the original single `role` enum.
Deleting this package would delete the migration history for the one table the
whole admin depends on.

So what is left is deliberate and minimal:

```
payload.config.ts          the Payload instance binding now_platform
src/collections/Users.ts   the identity schema: email, credential, two roles
src/migrations/            how that table got its shape
```

Everything else — the `(console)` pages, the `(payload)` admin routes, the
`lib/` query helpers, the Next config — is gone, because all of it either
moved to `apps/web` or served a surface nobody deploys.

## What you do with it

```bash
# apply pending migrations to the platform database
DATABASE_URI=... npm run migrate -w @now-engine/console
DATABASE_URI=... npm run migrate:status -w @now-engine/console
```

Note `DATABASE_URI` here points at **`now_platform`**, not a city database.
Unlike the CMS this is not a per-city knob: there is exactly one platform
database.

## What you do NOT do with it

**Creating a staff account.** That is
`npm run staff-account -w @now/auth` — see
[packages/auth/README.md](../../packages/auth/README.md). There is no admin UI
here to create one in, and the city CMS cannot create one either because its
`users` collection is a read-only shadow of this table.

**Editing commerce data.** `orgs`, `partnerships`, `campaigns` and
`placements` live in `now_platform.engine`, Alembic-owned, and this config
deliberately does not model them. The header comment in `payload.config.ts`
explains why moving them would break link resolution on the request path.
