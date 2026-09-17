import 'server-only'

import type { CommerceRole, EditorialRole } from '@now/auth'

import { query } from './db'

/**
 * Every read and write the staff surface makes against
 * `now_platform.public.users`, in one file.
 *
 * **Why this is not a Payload collection.** Payload binds exactly one
 * database per instance and this app's instance is bound to the *city*
 * database (docs/ADMIN-CONSOLIDATION.md, "The one real constraint"). Staff
 * identity lives in the platform database, which that instance cannot reach.
 * `packages/cms/src/collections/Users.ts` is the city-side shadow of these
 * rows and is deliberately read-only — writing there would create a second
 * source of truth that the next sign-in silently overwrites.
 *
 * So this is direct SQL on the platform pool, the same shape the commerce
 * pages use (`lib/queries.ts`). The difference is that those are reads and
 * these are writes: `lib/db.ts` describes the commerce *tables* as read-only
 * because `engine.*` is Alembic-owned and `now_link_resolver` reads it on the
 * request path. `public.users` is not one of those — it is the platform's own
 * identity table, and this is its management surface.
 *
 * **`hash` and `salt` are never selected.** Not once, anywhere in this file.
 * The only fact the UI needs is whether a credential exists, and that comes
 * back as a boolean computed in the database, so there is no code path by
 * which a stored credential can reach a React tree, an HTML attribute or an
 * RSC payload. That is cheaper to guarantee than to review.
 */

export type StaffMember = {
  id: number
  email: string
  name: string | null
  editorialRole: EditorialRole
  commerceRole: CommerceRole
  /** `hash IS NOT NULL` — whether this person can sign in at all. */
  hasCredential: boolean
  failedAttempts: number
  /**
   * Minutes left on an ACTIVE lockout, 0 when not locked.
   *
   * Computed in Postgres rather than shipping `lock_until` to the browser
   * and formatting it there: a timestamp rendered on the server and again on
   * the client is a hydration mismatch waiting to happen, and "locked for
   * another 7 minutes" is the only thing anyone reads it for anyway.
   */
  lockedForMinutes: number
}

type StaffRow = {
  id: string | number
  email: string
  name: string | null
  editorial_role: EditorialRole
  commerce_role: CommerceRole
  has_credential: boolean
  failed_attempts: number
  locked_for_minutes: number
}

function toMember(row: StaffRow): StaffMember {
  return {
    id: Number(row.id),
    email: row.email,
    name: row.name,
    editorialRole: row.editorial_role,
    commerceRole: row.commerce_role,
    hasCredential: row.has_credential,
    failedAttempts: Number(row.failed_attempts ?? 0),
    lockedForMinutes: Number(row.locked_for_minutes ?? 0),
  }
}

/* The projection every read shares, so "what does this surface expose" has a
   single answer. `login_attempts` is `numeric` in Payload's schema and comes
   back from node-postgres as a string, hence the cast. */
const SELECT_MEMBER = `
  SELECT id,
         email,
         name,
         editorial_role,
         commerce_role,
         (hash IS NOT NULL AND salt IS NOT NULL) AS has_credential,
         coalesce(login_attempts, 0)::int        AS failed_attempts,
         coalesce(
           greatest(0, ceil(extract(epoch from (lock_until - now())) / 60))::int,
           0
         )                                       AS locked_for_minutes
    FROM public.users`

export async function listStaff(): Promise<StaffMember[]> {
  const rows = await query<StaffRow>(`${SELECT_MEMBER} ORDER BY lower(email)`)
  return rows.map(toMember)
}

export async function findStaff(id: number): Promise<StaffMember | null> {
  const rows = await query<StaffRow>(`${SELECT_MEMBER} WHERE id = $1`, [id])
  return rows[0] ? toMember(rows[0]) : null
}

export type NewStaffAccount = {
  email: string
  name: string | null
  editorialRole: EditorialRole
  commerceRole: CommerceRole
  hash: string
  salt: string
}

/**
 * Creates an account, and **refuses rather than updates** when the address is
 * already taken — returns null in that case.
 *
 * `scripts/staff-account.mjs` upserts on email, which is right for a command
 * someone types deliberately with a flag list in front of them. It is wrong
 * for a button labelled "Invite": the failure mode is an admin typing a
 * colleague's address to add them, not noticing they were already there, and
 * silently resetting that person's password and both their roles. Resetting
 * a credential is a separate, named action on this surface for exactly that
 * reason.
 */
export async function createStaffAccount(account: NewStaffAccount): Promise<StaffMember | null> {
  const rows = await query<{ id: string | number }>(
    `INSERT INTO public.users
       (email, name, hash, salt, editorial_role, commerce_role,
        login_attempts, lock_until, updated_at, created_at)
     VALUES ($1, $2, $3, $4, $5, $6, 0, NULL, now(), now())
     ON CONFLICT (email) DO NOTHING
     RETURNING id`,
    [
      account.email,
      account.name,
      account.hash,
      account.salt,
      account.editorialRole,
      account.commerceRole,
    ],
  )
  const id = rows[0]?.id
  if (id === undefined) return null
  return findStaff(Number(id))
}

export async function updateStaffRoles(
  id: number,
  editorialRole: EditorialRole,
  commerceRole: CommerceRole,
): Promise<StaffMember | null> {
  const rows = await query<{ id: string | number }>(
    `UPDATE public.users
        SET editorial_role = $2,
            commerce_role  = $3,
            updated_at     = now()
      WHERE id = $1
      RETURNING id`,
    [id, editorialRole, commerceRole],
  )
  return rows[0] ? findStaff(Number(rows[0].id)) : null
}

/**
 * Writes a new credential and clears the lockout with it.
 *
 * The lockout clear is not a convenience: without it, the fix for "I am
 * locked out" would leave the person locked out with a password they cannot
 * use yet. `scripts/staff-account.mjs` does the same, and says so.
 */
export async function resetStaffCredential(
  id: number,
  hash: string,
  salt: string,
): Promise<StaffMember | null> {
  const rows = await query<{ id: string | number }>(
    `UPDATE public.users
        SET hash           = $2,
            salt           = $3,
            login_attempts = 0,
            lock_until     = NULL,
            updated_at     = now()
      WHERE id = $1
      RETURNING id`,
    [id, hash, salt],
  )
  return rows[0] ? findStaff(Number(rows[0].id)) : null
}

/** Unlock without touching the credential — for someone who simply mistyped. */
export async function clearStaffLockout(id: number): Promise<StaffMember | null> {
  const rows = await query<{ id: string | number }>(
    `UPDATE public.users
        SET login_attempts = 0,
            lock_until     = NULL,
            updated_at     = now()
      WHERE id = $1
      RETURNING id`,
    [id],
  )
  return rows[0] ? findStaff(Number(rows[0].id)) : null
}
