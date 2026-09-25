import 'server-only'

import {
  PostgresReaderStore,
  READER_SESSION_COOKIE,
  verifyReaderToken,
  type ReaderRecord,
} from '@now/auth'
import { Mailer, createTransportFromEnv } from '@now/mailer'
import { cookies } from 'next/headers'
import pg from 'pg'
import { cache } from 'react'

import { getSiteConfig } from '@/lib/site'

/**
 * Reader identity for the public site (E8.3 — docs/READER-IDENTITY.md).
 *
 * Deliberately NOT `lib/auth.ts`. That file answers "which staff member is
 * signed in, and what may they see"; this one answers "which reader is signed
 * in". They share no cookie, no signing secret and no store, and the one thing
 * that must never happen is a reader session satisfying a staff check — so
 * they do not share a module either, and neither imports the other.
 */

// --- the platform pool -----------------------------------------------------
//
// Readers live in `now_platform.engine`, not a city database: a person reads
// Jakarta and Bali. Module-scope, because a pool per request leaks connections
// under any real load.
let platformPool: pg.Pool | null = null

function pool(): pg.Pool {
  const url = process.env.PLATFORM_DATABASE_URI ?? process.env.PLATFORM_DATABASE_URL
  if (!url) throw new Error('PLATFORM_DATABASE_URI is not set')
  platformPool ??= new pg.Pool({ connectionString: url, max: 4, statement_timeout: 5_000 })
  return platformPool
}

export function readerStore(): PostgresReaderStore {
  return new PostgresReaderStore(pool())
}

// --- secrets ---------------------------------------------------------------

/**
 * The reader signing secret, which must NOT be `PAYLOAD_SECRET`.
 *
 * Sharing it would leave `aud` as the only thing standing between a reader
 * token and a staff route — one claims-validation bug away from a privilege
 * escalation. Refusing to start is the correct response to a deployment that
 * set them the same, because the alternative is running with a defence that
 * silently is not there.
 */
export function readerSecret(): string {
  const secret = process.env.READER_SESSION_SECRET
  if (!secret) throw new Error('READER_SESSION_SECRET is not set')
  if (secret === process.env.PAYLOAD_SECRET) {
    throw new Error(
      'READER_SESSION_SECRET must not equal PAYLOAD_SECRET — separate populations need separate signing keys',
    )
  }
  if (secret.length < 32) {
    throw new Error('READER_SESSION_SECRET must be at least 32 characters')
  }
  return secret
}

// --- where links point -----------------------------------------------------

/**
 * The origin used to build verification and reset links.
 *
 * From configuration — `SITE_BASE_URL`, falling back to the site config's own
 * hostname — and **never** from a request `Host` header. See
 * `packages/mailer/src/links.ts` for the attack that closes.
 */
export async function siteBaseUrl(): Promise<string> {
  const configured = process.env.SITE_BASE_URL
  if (configured) return configured.replace(/\/+$/, '')
  // Outside production, refuse to guess. The registry's `hostname` is the
  // city's PUBLIC domain -- today the live WordPress site -- so a dev server
  // without SITE_BASE_URL minted verification links to nowbali.co.id, and a
  // browser following one sent a real single-use token to a site that is not
  // this code (QA, 2026-09-25). Same stance as readerSecret(): fail loudly.
  if (process.env.NODE_ENV !== 'production') {
    throw new Error(
      'SITE_BASE_URL is not set. Reader emails link to it; set it to the origin this ' +
        'server is reached on (e.g. http://localhost:3100) in .env.local.',
    )
  }
  const site = await getSiteConfig()
  return `https://${site.hostname}`
}

export function allowInsecureLinks(): boolean {
  return process.env.NODE_ENV !== 'production'
}

// --- mail ------------------------------------------------------------------

/**
 * Can this deployment actually complete a sign-up?
 *
 * Registration, verification and password reset all need mail. Without it the
 * surface does not fail — it *succeeds wrongly*: a real person registers, their
 * address and password hash land in the production database, the page says
 * "check your email", and no email is ever sent. They cannot verify, cannot
 * reset, and have no way to tell that anything went wrong. Found live on
 * 2026-09-16, with `/account/register` serving a public form on both cities
 * while no SMTP credential existed (F141).
 *
 * So the account surface is gated on mail being configured, and the gate is
 * derived rather than a separate flag somebody has to remember to flip. The
 * moment SMTP is set, the routes come back on their own; until then they are
 * not reachable to be half-used.
 *
 * Development is unaffected: the console transport is a valid transport, so
 * this is true whenever `createTransportFromEnv` succeeds.
 */
export function accountsEnabled(): boolean {
  if (process.env.READER_ACCOUNTS_ENABLED === 'false') return false
  return createTransportFromEnv().ok
}

let mailer: Mailer | null = null

export function readerMailer(): Mailer {
  if (mailer) return mailer
  const selected = createTransportFromEnv()
  // Thrown, not swallowed: a misconfigured transport means verification mail
  // silently never arrives, and every account created in the meantime is
  // stranded. Better to fail the request loudly than to accumulate them.
  if (!selected.ok) throw new Error(`mail transport unavailable: ${selected.detail}`)
  mailer = new Mailer({
    transport: selected.transport,
    from: {
      email: process.env.MAIL_FROM_EMAIL ?? 'hello@example.com',
      name: process.env.MAIL_FROM_NAME ?? 'NOW!',
    },
  })
  return mailer
}

export async function mailBranding(): Promise<{ siteName: string; supportEmail: string }> {
  const site = await getSiteConfig()
  return {
    siteName: site.name,
    supportEmail: process.env.MAIL_SUPPORT_EMAIL ?? process.env.MAIL_FROM_EMAIL ?? '',
  }
}

// --- who is signed in ------------------------------------------------------

export type SignedInReader = {
  id: string
  email: string
  name: string | null
  emailVerified: boolean
  /** When they joined. Null when the store does not supply it. */
  joinedAt: Date | null
}

/**
 * The reader for this request, or null.
 *
 * The token is proof of identity; it is **not** proof the account is still
 * usable. Status and verification are re-read from the database on every call,
 * because a 30-day token would otherwise keep a deleted or suspended account
 * signed in for a month. That is the same reasoning the staff side applies to
 * re-reading roles at sign-in, applied to a longer-lived token.
 *
 * `cache()`-wrapped (React's request-scoped memoization, the same primitive
 * `fetch` gets for free) so "the database" above means once per request, not
 * once per caller. `(site)/layout.tsx` reads this for the masthead and says
 * so explicitly — "one session read per request… not a second
 * `currentReader()` call inside Masthead itself" — but that was a rule about
 * call DISCIPLINE, and `/account`'s own page already breaks it today (it
 * reads the reader again for its own body). The article page reading it a
 * third time, to know whether to render a Save toggle and in which state,
 * is the same legitimate need with the same fix: memoize the read itself
 * rather than asking every future caller to remember not to.
 */
export const currentReader = cache(async (): Promise<SignedInReader | null> => {
  const jar = await cookies()
  const token = jar.get(READER_SESSION_COOKIE)?.value
  if (!token) return null

  const verified = verifyReaderToken(token, readerSecret())
  if (!verified.ok) return null

  let record: ReaderRecord | null
  try {
    record = await readerStore().findById(verified.claims.identityId)
  } catch {
    // A database blip should log a reader out for this request, not 500 the
    // page they were reading.
    return null
  }
  if (!record || record.status !== 'active') return null

  return {
    id: record.id,
    email: record.email,
    name: record.name,
    emailVerified: record.emailVerifiedAt !== null,
    joinedAt: record.createdAt,
  }
})

export async function isSignedIn(): Promise<boolean> {
  return (await currentReader()) !== null
}
