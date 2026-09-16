# Reader identity, accounts and the dashboard

**Status:** planned, not started. Decided 2026-09-16.
**Phase:** E8 — numbered after E7 but **scheduled before it**. E7's models
consume what E8 collects; there is nothing for a taste vector to be built
*from* until readers can sign in and the beacon is live.

## Why this is the backbone

`interactions.user_id` has been in the frozen E0.2 contract since day one and
has been **NULL on every row ever written**, because no reader can sign in.
Everything downstream inherits that hole:

| Wants | Needs |
|---|---|
| `user_profiles.taste_vec_*` (shipped, empty) | a `user_id` to attach a history to |
| §17 cold start "direct from registration" | a registration |
| `itineraries.user_id` (nullable, always NULL) | an account to own a trip |
| §17 "saved / shared" at weight **1.0** | somewhere to put a save — **there is no table** |

So this is not a new subsystem. It is the missing **join key** between three
subsystems that already exist.

## Decided: readers are not staff

Two identity stores, deliberately.

```
now_platform.public.users       STAFF    — Payload-shaped, editorial+commerce
                                           roles, shadow-projected into each
                                           city DB (ADMIN-CONSOLIDATION.md)
now_platform.engine.identities  READERS  — one row per person, spans cities
```

Rejected: **one table for both.** Tempting — the credential code is already
written and it would be one login. But the staff table is projected into every
city database as a shadow row so Payload can bind to it, and that projection is
sized for dozens of staff, not for the reader population. It would also put a
reader one mistaken `role` value away from a CMS session. The blast radius of
getting that wrong is the entire editorial surface, and the saving is one table.

Rejected: **readers in the city DB.** A person reads Jakarta *and* Bali. The
newsletter already made this call for exactly this reason — migration 0006 put
`newsletter_subscribers` in `now_platform.engine`, not the city, because "a
subscriber is a person and a person can read both cities". Same person, same
argument.

### What IS shared: the crypto, not the store

`@now/auth` already contains the security-critical half, hardened for staff:
PBKDF2 matched byte-for-byte to Payload's parameters, `timingSafeEqual`
comparison, a lockout policy behind an injectable `IdentityStore` interface,
and signed session cookies. A reader auth path reuses all of it and adds a
`ReaderIdentityStore` implementing the same interface.

Writing a second password hasher is how you end up with two security levels and
only one of them audited.

## The boundary that must not leak

**A reader session must never authenticate into `/team-editor`.** Three
independent defences, because one is a single typo away from nothing:

| | |
|---|---|
| **Different cookie** | staff hold `__Host-now-staff`; readers get `__Host-now-reader`. Distinct names mean a reader cookie is not even *presented* to the staff path. |
| **Different signing secret** | a reader token signed with the staff secret is a forgery waiting for one claims-validation bug. Separate secrets make it cryptographically impossible rather than logically unlikely. |
| **Explicit `aud` claim** | `aud: 'reader'` vs `aud: 'staff'`, checked on verify. Defence in depth for the day someone reuses a secret by accident. |

`SessionClaims` today is staff-shaped (`shadowId`, `editorialRole`,
`commerceRole`). Reader claims carry `identityId` and **no role at all** — a
reader has no role, and adding a nullable one invites a `role === undefined`
check somewhere that treats it as permissive.

## Prerequisite: nothing sends email

There is **no mailer anywhere in the stack** — no nodemailer, Resend, SendGrid,
SMTP config, nothing. This is not only an auth problem:

> `lib/newsletter.ts` writes every subscriber as `status='pending'` and no code
> path ever sends the confirmation or moves them to `'confirmed'`. The
> newsletter has been **silently collecting unconfirmed addresses**. The
> `pending → confirmed` states in migration 0006 describe a double opt-in that
> was never built. (F135)

Email + password was chosen for sign-in, which needs mail for verification and
for password reset. So the mailer is **E8.0 — the first task**, and it repairs
the newsletter on the way past.

## Schema — migration 0007

`identities` today is `id · email · created_at · stated_prefs`. It cannot store
a credential.

```sql
ALTER TABLE engine.identities
  ADD email_norm        text,           -- lower(email), the real unique key
  ADD name              text,
  ADD hash              text,           -- PBKDF2, @now/auth parameters
  ADD salt              text,
  ADD email_verified_at timestamptz,
  ADD login_attempts    int NOT NULL DEFAULT 0,
  ADD lock_until        timestamptz,
  ADD last_login_at     timestamptz,
  ADD status            text NOT NULL DEFAULT 'active';

-- Unique on the NORMALISED address. `uq_identities_email` is on the raw
-- column, which would let Foo@ and foo@ both register.
CREATE UNIQUE INDEX uq_identities_email_norm ON engine.identities (email_norm);

-- Single-use, hashed at rest: a token sitting in a mailbox is a bearer
-- credential, and a leaked backup should not be a password reset.
CREATE TABLE engine.identity_tokens (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  identity_id uuid NOT NULL REFERENCES engine.identities(id) ON DELETE CASCADE,
  kind        text NOT NULL CHECK (kind IN ('verify_email','reset_password')),
  token_hash  text NOT NULL,
  expires_at  timestamptz NOT NULL,
  consumed_at timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- §17 weights a save at 1.0 and there has never been anywhere to put one.
CREATE TABLE engine.saved_items (
  identity_id uuid NOT NULL REFERENCES engine.identities(id) ON DELETE CASCADE,
  site_id     uuid NOT NULL REFERENCES engine.sites(id),
  entity_type text NOT NULL,
  entity_id   text NOT NULL,
  note        text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (identity_id, site_id, entity_type, entity_id)
);
```

`entity_id` is **text**, following the widening precedent set by migration 0005
for sibling entity refs rather than betting that every future entity type is a
bigint.

## Identity stitching — the part that is easy to forget

A reader browses anonymously for weeks, then registers. Their history is sitting
in `interactions` under an `anon_id`, and if nothing connects the two their
brand-new account looks like a cold start **when it is not**.

```
1. sign-in succeeds
2. server reads the nowb_aid cookie                    (the beacon's anon_id)
3. UPDATE interactions SET user_id = $identity
     WHERE anon_id = $anon AND user_id IS NULL
4. client calls now.identify(identityId)               (already implemented)
```

Step 4 needs no beacon work at all — `now.identify()` and the `user_id` field
have been in the client since E0.4, guarded to accept only a valid UUID.

**Bound step 3.** A shared or public machine accumulates one `anon_id` used by
several people, and attributing a stranger's reading history to a named account
is a privacy incident, not a data win. Stitch a capped recent window, not all
history.

## Registration — ARCHITECTURE §17, unchanged

Already specified there, and the 30-second budget is the spec:

```
1. What are you into?  eat·drink·stay·do·wellness·culture·events   pick 3+
2. Where do you spend time?   area chips, 1–3
3. You're...  expat · local · visiting · business
4. Budget  $ · $$ · $$$ · $$$$   (skippable)
```

Answers land in `identities.stated_prefs` and seed
`user_profiles.facet_affinity`. These are **term ids**, not free text, so they
join to `engine.entity_terms` — which is populated (17,237 Jakarta / 15,804
Bali). That matters: a stated-preference cold start works **without waiting on
F50**, unlike the three rails.

The picker is Netflix/Spotify-shaped on purpose — pick your genres, get a feed.
The difference from those products is that the picks are **term ids in the
shared vocabulary**, so the same taxonomy that classifies an article is the one
a reader chooses from. No parallel "interests" list to drift out of sync.

## Stated vs revealed — already decided, §10

What a reader *says* they like and what they *actually read* are two different
signals, and ARCHITECTURE §10 already specifies how they combine:

```python
α = n_meaningful / (n_meaningful + 20)
taste = α · revealed + (1 − α) · stated_seed
```

**No cutoff, no cliff, and registration picks remain a prior forever.** A reader
with 0 interactions is 100% what they told you. At 20 meaningful interactions
it is a 50/50 blend. At 100 it is 83% behaviour. Nobody is ever dropped off an
edge, and someone who reads nothing for six months still has a usable profile.

`user_profiles.n_meaningful` (shipped, defaults 0) is the α input. It counts
*meaningful* interactions, not page views — §17's weights are the definition:

```
impression, no click   −0.1     saved / shared         1.0
click                   0.3     added to itinerary     1.2   ← strongest
dwell ≥ 30s             0.6     thumbs down           −1.0
scroll ≥ 70%            0.8
```

And revealed taste runs at **two speeds** (§10), because a reader planning a
trip has a session intent unrelated to their year-round taste:

```python
long_term  = Σ wᵢ · decay(tᵢ, half_life=180d) · embed(itemᵢ)
short_term = Σ wᵢ · embed(itemᵢ)              # last ~10 interactions
β = 0.6 if session_interactions ≥ 3 else 0.2
```

Every one of these inputs — `interactions.kind`, `dwell_ms`, `scroll_pct` —
is already in the frozen E0.2 beacon contract. **Nothing new needs collecting.**

## What the reader sees

The profile feeds the site, not just the dashboard. Two things to be honest
about before wiring it to the homepage:

**F50 gates the type-filtered rails, not facet affinity.** `primary_type` is
NULL archive-wide, so anything filtering on type returns zero rows. But
`entity_terms` is populated, so a facet-affinity feed ("more Japanese food,
more Senopati") is reachable **now**. Build the feed on `entity_terms`; it
degrades to popularity when a reader is new, not to empty.

**Do not train on what you showed.** §17's presentation-bias warning applies
the moment a personalized feed exists: readers can only click what was shown,
so a ranker trained on its own output learns to reproduce itself. Impressions
with rail and position are already logged by the beacon precisely so this is
correctable (IPW). Log them from the first personalized render, not later.

**Leave a way out.** A feed that only reflects a reader back to themselves is a
worse magazine. Keep an unpersonalized view reachable, and keep editorial
placement able to override — §12's "deterministic engine decides" cuts both
ways.

## Staff editing — and the constraint it hits

Everything above must be editable by staff in `/team-editor`: the topic and
genre options offered at registration, their labels and order, and an
individual reader's preferences for support.

**Nothing here is editable today.** There is no Payload collection for `terms`
or `facets` — the vocabulary lives in `now_platform.engine.terms` and is
managed by migrations and CLI (`0002_terms_attrs…`, `vocabulary_delta_140_terms`).

And it cannot simply become one, because of the constraint
ADMIN-CONSOLIDATION.md already ran into: **Payload binds to exactly one
database per instance**, and that is the *city* DB. The vocabulary and the
readers are both in the *platform* DB.

**Decided: plain Next pages inside the admin shell, direct SQL, behind
`requireUser()`** — the pattern the commerce console already uses. Per
ADMIN-CONSOLIDATION: *"Every commerce page (`orgs`, `campaigns`) is a plain
Next page reading `now_platform.engine.*` over direct SQL, behind an auth
check."* Those pages live at `/team-editor/commerce/…` and prove the shape
works.

```
/team-editor/audience/topics      which terms appear in the picker,
                                  label, order, featured — writes
                                  engine.terms.attrs
/team-editor/audience/readers     a reader's stated_prefs and computed
                                  affinity, for support
```

Rejected: **shadow-projecting the vocabulary into each city DB** the way
`public.users` is. The users shadow is safe because it is strictly
write-from-platform on sign-in and read-only in the admin — a one-way
projection. Vocabulary editing needs write-*back*, and a bidirectional sync of
the taxonomy that every classification depends on is a much larger risk than
the direct-SQL page it replaces.

⚠️ **Editing the picker edits the live taxonomy.** `engine.terms` is the same
vocabulary the classifier writes against. Retiring a term from the registration
picker must not retire it from classification — that is what
`docs/vocabulary-retirement-playbook.md` governs. Presentation flags belong in
`terms.attrs`; the term itself is not the staff dashboard's to delete.

## Dashboard v1

| Panel | Depends on | Works today? |
|---|---|---|
| Editable taste profile — "we think you like Japanese food, Senopati, rooftop bars" | `stated_prefs` + `entity_terms` | ✅ yes |
| Saved items | `saved_items` (new) | ✅ yes |
| Reading history | `interactions` + **beacon deployed** | ⚠️ needs B2 |
| Saved itineraries | E5.4 persistence | ❌ placeholder until E5.4 |

The taste profile is editable on purpose. §17: *"Corrections are high-quality
training signal."* A reader telling you that you were wrong about them is worth
more than a click.

## Honest limits

**The beacon must ship with this.** B2 approved 2026-09-16. Accounts without the
beacon record who someone is and nothing about what they do — the reading-history
panel would be permanently empty and E7's clock would still not be running.

**This does not unblock the rails.** F50 stands: `primary_type` is NULL
archive-wide, type classification measured 0.66 and earns auto-apply at no
threshold, so the three rails still do not run on real articles. E8 makes
personalization *possible*; it does not make the recommendation surface it
personalises *work*. Those are separate repairs, and E8 is not a substitute for
E2.1.

**Privacy obligations start the day this ships.** Storing a named person's
reading history is categorically different from an `anon_id`. Export and delete
must exist at launch rather than be retrofitted — `ON DELETE CASCADE` above is
the cheap half; the partitioned `interactions` rows are the hard half.
