import 'server-only'

import Redis from 'ioredis'

/**
 * Shared rate limiting for the reader auth surface (E8.3a).
 *
 * The first version was a `Map` in process memory, which I shipped knowing it
 * was wrong and wrote down as such: with N containers it allows N times the
 * intended rate, and it forgets everything on restart — so an attacker gets a
 * fresh budget from every redeploy and from every container the load balancer
 * happens to pick. Redis is the shared counter those limits always assumed.
 *
 * ## What this is and is not for
 *
 * It is NOT the protection against guessing one person's password. That is the
 * per-account lockout in `identities` (`DEFAULT_READER_LOCKOUT`, 10 attempts),
 * which lives in Postgres, is durable, and is seen identically by every
 * container. This blunts the shape lockout cannot see: many addresses, few
 * attempts each — credential stuffing, and mass password-reset mail aimed at
 * other people's inboxes.
 *
 * That division decides the failure behaviour below.
 */

const PREFIX = 'now:ratelimit:'

/**
 * INCR and expiry in one round trip, so two requests racing on the first hit
 * cannot both skip the PEXPIRE and leave a counter that never resets. The
 * naive INCR-then-EXPIRE pair loses that race rarely and the consequence is a
 * key that blocks a legitimate address forever.
 */
const SCRIPT = `
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('PEXPIRE', KEYS[1], ARGV[1]) end
return n
`

let client: Redis | null = null
let clientFailed = false

function getClient(): Redis | null {
  if (clientFailed) return null
  if (client) return client
  const url = process.env.REDIS_URL
  if (!url) {
    // Once, not per call: this is the steady state in a dev environment that
    // has not set it, and a line per login attempt would be noise nobody reads.
    if (!clientFailed) {
      console.warn(
        '[ratelimit] REDIS_URL is not set — falling back to an in-process limiter, ' +
          'which allows N× the intended rate across N containers. See .env.example.',
      )
    }
    clientFailed = true
    return null
  }
  client = new Redis(url, {
    lazyConnect: true,
    maxRetriesPerRequest: 1,
    // A sign-in must not hang waiting for a counter. If Redis is slow the
    // right answer is to fall back, quickly.
    connectTimeout: 1500,
    commandTimeout: 1000,
  })
  client.on('error', (err) => console.error(`[ratelimit] redis error: ${err.message}`))
  return client
}

// --- in-process fallback ----------------------------------------------------
//
// Kept deliberately. When Redis is unreachable the choice is between no limit
// at all and a weak one, and a weak one is strictly better — it still stops a
// single process being hammered, which is the common case.

type Bucket = { count: number; resetAt: number }
const buckets = new Map<string, Bucket>()

function localLimit(key: string, limit: number, windowMs: number): boolean {
  const now = Date.now()
  const bucket = buckets.get(key)
  if (!bucket || bucket.resetAt <= now) {
    buckets.set(key, { count: 1, resetAt: now + windowMs })
    if (buckets.size > 10_000) {
      for (const [k, v] of buckets) if (v.resetAt <= now) buckets.delete(k)
    }
    return true
  }
  if (bucket.count >= limit) return false
  bucket.count += 1
  return true
}

/**
 * True when the caller is within its budget.
 *
 * **Fails OPEN, loudly, onto the local limiter.** A Redis outage must not lock
 * every reader out of signing in — the durable per-account lockout is
 * untouched by this and still protects the case that matters, so trading
 * everyone's access for a supplementary control would be the wrong way round.
 *
 * What it must never do is fail open *silently*, which is the fault this
 * codebase produced three times in one day: a surface reporting an ordinary
 * outcome while something underneath was broken. Every fallback logs.
 */
export async function rateLimit(key: string, limit: number, windowMs: number): Promise<boolean> {
  const redis = getClient()
  if (!redis) return localLimit(key, limit, windowMs)

  try {
    if (redis.status === 'wait') await redis.connect()
    const n = (await redis.eval(SCRIPT, 1, PREFIX + key, String(windowMs))) as number
    return n <= limit
  } catch (error) {
    // Logged without the key: it contains the email address being limited.
    console.error(
      `[ratelimit] redis unavailable, falling back to in-process: ${
        error instanceof Error ? error.message : String(error)
      }`,
    )
    return localLimit(key, limit, windowMs)
  }
}

/** Test seam: drops the local buckets so cases cannot leak into each other. */
export function __resetLocalBuckets(): void {
  buckets.clear()
}
