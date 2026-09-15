/**
 * The Postgres-backed `IdentityStore`, and the city-side shadow projection.
 *
 * This is the only file in the package that knows Postgres exists. Everything
 * that makes a *decision* lives in `identity.ts` behind the `IdentityStore`
 * interface, which is why the lockout and role policy can be tested
 * exhaustively without a container.
 *
 * Two pools, deliberately:
 *   - the PLATFORM pool reads `now_platform.public.users` — the source of
 *     truth for who exists, their role, and their credential
 *   - a CITY pool writes `<city>.public.users` — the shadow Payload needs in
 *     its own database, because Payload binds one database per instance
 */

// `pg` is CommonJS. A named import works under a bundler's interop but throws
// under plain Node ESM —
//   SyntaxError: The requested module 'pg' does not provide an export named 'Pool'
// — which is how the payload CLI loads this package. Default-import then
// destructure is the portable form, and this package is consumed both ways.
import pg from 'pg'
import type { PoolConfig } from 'pg'

const { Pool } = pg
type Pool = pg.Pool

import type { AuthenticatedUser, IdentityStore, PlatformUser } from './identity.ts'
import { isCommerceRole, isEditorialRole } from './identity.ts'

export function createPool(connectionString: string, overrides: PoolConfig = {}): Pool {
  return new Pool({
    connectionString,
    // A sign-in must fail fast rather than hang a request thread. `identity.
    // authenticate` turns a throw here into `unavailable`, which is a
    // different message to the user than "wrong password".
    connectionTimeoutMillis: 5_000,
    statement_timeout: 5_000,
    max: 4,
    ...overrides,
  })
}

export class PostgresIdentityStore implements IdentityStore {
  // An explicit field rather than a constructor parameter property: the
  // latter needs a code transform, not just type erasure, so it is rejected
  // by `node --experimental-strip-types` — which is how this package's tests
  // run without a build step.
  readonly #pool: Pool

  constructor(pool: Pool) {
    this.#pool = pool
  }

  async findByEmail(email: string): Promise<PlatformUser | null> {
    const { rows } = await this.#pool.query(
      `SELECT id, email, name, editorial_role, commerce_role,
              hash, salt, login_attempts, lock_until
         FROM public.users
        WHERE lower(email) = $1
        LIMIT 1`,
      [email],
    )
    const row = rows[0]
    if (!row) return null

    return {
      id: Number(row.id),
      email: String(row.email),
      name: row.name === null ? null : String(row.name),
      // Left as-is when unrecognised rather than coerced to a default:
      // `authenticate` refuses an unknown role, and silently substituting
      // something permissive here would turn a data problem into a grant.
      editorialRole: row.editorial_role,
      commerceRole: row.commerce_role,
      hash: row.hash === null ? null : String(row.hash),
      salt: row.salt === null ? null : String(row.salt),
      // `login_attempts` is `numeric` in Payload's schema, which node-postgres
      // hands back as a string. `Number()` rather than a bare `+` so a null
      // becomes 0 instead of NaN.
      loginAttempts: Number(row.login_attempts ?? 0),
      lockUntil: row.lock_until === null ? null : new Date(row.lock_until),
    }
  }

  async recordFailedAttempt(userId: number, lockUntil: Date | null): Promise<void> {
    // Incremented in SQL, not read-modify-written in JS: two simultaneous
    // guesses must count as two, and a lost update here is a free attempt.
    await this.#pool.query(
      `UPDATE public.users
          SET login_attempts = coalesce(login_attempts, 0) + 1,
              lock_until     = $2
        WHERE id = $1`,
      [userId, lockUntil],
    )
  }

  async clearFailedAttempts(userId: number): Promise<void> {
    await this.#pool.query(
      `UPDATE public.users
          SET login_attempts = 0,
              lock_until     = NULL
        WHERE id = $1`,
      [userId],
    )
  }
}

/**
 * Writes the city-side shadow row for a user who has just signed in.
 *
 * **The shadow carries no secret.** `hash` and `salt` are left NULL, so a
 * dump of a city database yields nothing that authenticates anywhere — and
 * `verifyPassword` treats a credential-less row as unauthenticatable, which
 * means even Payload's own local strategy could not be tricked into accepting
 * one of these rows if it were ever re-enabled by mistake.
 *
 * Role is written on every sign-in, never merged, so a revocation made in the
 * platform takes effect the next time the user authenticates rather than
 * lingering in a stale projection.
 *
 * Returns the city-local row id, which is what Payload's session is issued
 * against.
 */
export async function upsertShadowUser(
  cityPool: Pool,
  user: AuthenticatedUser,
): Promise<number> {
  if (!isEditorialRole(user.editorialRole) || !isCommerceRole(user.commerceRole)) {
    throw new Error(
      `refusing to shadow unrecognised roles: editorial=${String(user.editorialRole)} ` +
        `commerce=${String(user.commerceRole)}`,
    )
  }

  const { rows } = await cityPool.query(
    `INSERT INTO public.users (email, name, role, hash, salt, login_attempts, updated_at, created_at)
     VALUES ($1, $2, $3, NULL, NULL, 0, now(), now())
     ON CONFLICT (email) DO UPDATE
        SET name       = EXCLUDED.name,
            role       = EXCLUDED.role,
            hash       = NULL,
            salt       = NULL,
            updated_at = now()
     RETURNING id`,
    // The city collection keeps its own single `role` column: it governs
    // publishing only, so the editorial dimension is the one that belongs
    // here. Commerce access is read from the platform, never shadowed --
    // there is nothing in a city database that commerce permissions apply to.
    [user.email, user.name, user.editorialRole],
  )

  const id = rows[0]?.id
  if (id === undefined) {
    throw new Error(`shadow upsert returned no id for ${user.email}`)
  }
  return Number(id)
}
