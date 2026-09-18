import 'server-only'
// `pg` is CommonJS; a named import throws under plain Node ESM even though a
// bundler tolerates it. Same fix as packages/auth/src/store.ts.
import pg from 'pg'
import type { Pool } from 'pg'

const { Pool: PgPool } = pg

/**
 * Platform database access. **This app never opens a city database.**
 *
 * ARCHITECTURE.md §2 puts orgs, partnerships, campaigns, placements and the
 * sites registry in `now_platform`, and keeps editorial content in the city
 * databases. The console is commerce, so one pool is the whole data layer —
 * there is deliberately no `getCityDb` here to reach for.
 *
 * `import 'server-only'` is the guard that matters: every query below runs
 * in a Server Component, and a stray import from a client component would
 * otherwise ship a database URL to the browser. It turns that into a build
 * error instead.
 */

declare global {
  // eslint-disable-next-line no-var
  var __nowConsolePool: Pool | undefined
}

/**
 * Both spellings, because both are deployed.
 *
 * `deploy/docker-compose.yml` sets `PLATFORM_DATABASE_URI` *and*
 * `PLATFORM_DATABASE_URL` on every web service to the same value, and says
 * why: the shared Payload config reads the `_URI` one to load the taxonomy at
 * boot, while these pages' read-only pool was written against `_URL`. Local
 * environments set only one or the other — `packages/cms/.env.example` has
 * just `_URI`. `lib/payload.ts` already accepted either; this did not, so a
 * correctly configured dev machine could reach the vocabulary and not the
 * registry. One resolution, used by every platform reader in this app.
 */
export function platformConnectionString(): string | null {
  return process.env.PLATFORM_DATABASE_URL ?? process.env.PLATFORM_DATABASE_URI ?? null
}

function connectionString(): string {
  const url = platformConnectionString()
  if (!url) {
    throw new Error(
      'Neither PLATFORM_DATABASE_URL nor PLATFORM_DATABASE_URI is set. The ' +
        'console reads the platform database directly; see deploy/.env.example.',
    )
  }
  return url
}

/**
 * One pool per process, cached on globalThis so Next's dev-mode module
 * reloading does not leak a new pool on every edit. `max` is small on
 * purpose: this is an internal tool with a handful of users, and Postgres
 * connections are the scarce resource on a 2 vCPU box shared with the API,
 * the worker and two Payload instances.
 */
export function db(): Pool {
  if (!globalThis.__nowConsolePool) {
    globalThis.__nowConsolePool = new PgPool({
      connectionString: connectionString(),
      max: 4,
      idleTimeoutMillis: 30_000,
      connectionTimeoutMillis: 5_000,
    })
  }
  return globalThis.__nowConsolePool
}

export async function query<T>(sql: string, params: unknown[] = []): Promise<T[]> {
  const result = await db().query(sql, params)
  return result.rows as T[]
}
