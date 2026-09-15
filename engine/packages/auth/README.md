# @now/auth

Shared staff identity. Phase 1 of [docs/ADMIN-CONSOLIDATION.md](../../../docs/ADMIN-CONSOLIDATION.md).

`now_platform.public.users` is the single source of truth for who may sign in
and what role they hold. Each city database keeps a **shadow projection**
carrying email, name and role — **never a credential** — because Payload binds
exactly one database per instance and needs its `admin.user` collection
locally.

## Why this package exists

The merged per-city app binds its Payload to the **city** database, but staff
identity lives in the **platform** database. Payload's own login operation
cannot reach across that boundary, so the credential check has to happen here.

## The part to be careful about

`password.ts` reimplements one function from Payload's local strategy:

```
pbkdf2(password, salt, 25000, 512, 'sha256')   // hash stored hex
```

Drift in any of those parameters silently rejects every valid password — or
worse, accepts an invalid one. Two defences:

1. **`test/password.test.ts` pins us to a credential Payload itself
   generated.** A test that hashes with the code it is testing proves only
   that the code agrees with itself.
2. Comparison uses `timingSafeEqual`, as Payload's does. `===` on hex strings
   leaks the matching prefix length through timing.

## Two role dimensions, not one enum

The CMS and console arrived with disjoint vocabularies:

| dimension | values | governs |
|---|---|---|
| `editorialRole` | `admin` `editor` `author` `none` | publishing, in the city CMS |
| `commerceRole` | `admin` `partner_manager` `viewer` `none` | orgs, partnerships, campaigns |

One field cannot express both. "An editor who may also read partner terms"
and "a partner manager who may not publish" are both real people, and
collapsing them forces either over-granting or an enum that grows
multiplicatively.

`none` is the default on both, and a user who is `none` on both is refused at
sign-in with `no_access` rather than admitted to an empty admin.

**The city shadow takes the editorial dimension only.** Commerce access is
read from the platform on every request; there is nothing in a city database
that commercial permissions apply to.

## Design notes

**Failures are indistinguishable.** An unknown address and a wrong password
both return `invalid_credentials`, or the sign-in form becomes an oracle for
which staff addresses exist. `locked` is the one exception, and only ever
appears after an existing account is correctly identified.

**An outage is not a bad password.** A store that throws yields
`unavailable` — never `invalid_credentials` — and is never counted as a failed
attempt, so a database blip cannot lock out a blameless user.

**An unrecognised role is refused, not defaulted.** Substituting `viewer` for
an unknown value would turn a data problem into a quiet grant.

**The shadow carries no secret.** `hash` and `salt` are written NULL, so a
dump of a city database yields nothing that authenticates anywhere. Role is
overwritten on every sign-in, never merged, so a central revocation takes
effect on next sign-in rather than lingering in a stale projection.

**Decisions are separate from Postgres.** Everything in `identity.ts` runs
against an `IdentityStore` interface, which is why 31 tests cover lockout,
role revocation, clock handling and outage behaviour with no container.

## Tests

```bash
node --test --experimental-strip-types test/*.test.ts          # 34, no database
NOW_PG_PASSWORD=… node --test --experimental-strip-types test/*.test.ts   # 41, with
```

The integration file skips cleanly when the dev stack is down, rather than
failing. It proves the two things a fake store cannot: that the SQL matches
the schema Payload actually created, and that the shadow row lands carrying a
role but no credential.

> Note: this package's source avoids TypeScript constructor parameter
> properties and enums. Both need a code transform rather than type erasure,
> and `node --experimental-strip-types` rejects them — which is what lets the
> tests run with no build step.

## Not done yet

- Wiring the strategy into the Payload configs
  (`disableLocalStrategy: true` + a custom strategy resolving the shadow row)
- Migrating existing city `users` rows into the platform table
