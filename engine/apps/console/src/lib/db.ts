import 'server-only'
import { Pool } from 'pg'

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

function connectionString(): string {
  const url = process.env.PLATFORM_DATABASE_URL
  if (!url) {
    throw new Error(
      'PLATFORM_DATABASE_URL is not set. The console reads the platform ' +
        'database directly; see deploy/.env.example.',
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
    globalThis.__nowConsolePool = new Pool({
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
