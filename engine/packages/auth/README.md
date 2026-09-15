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
node --test --experimental-strip-types test/*.test.ts
```

## Not done yet

- Wiring the strategy into the CMS and console Payload configs
  (`disableLocalStrategy: true` + a custom strategy resolving the shadow row)
- Migrating existing city `users` rows into the platform table
- Integration tests against a real pair of databases
