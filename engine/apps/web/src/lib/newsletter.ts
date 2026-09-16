'use server'

import { redirect } from 'next/navigation'
import pg from 'pg'

import { getSiteConfig } from '@/lib/site'

/**
 * Newsletter signup.
 *
 * The form has been on every page since the comp, posting to `/api/subscribe`
 * — a route that has never existed. Every address anyone typed went nowhere,
 * and the form said nothing about it. This is the endpoint.
 *
 * A SERVER ACTION rather than a route handler, for two reasons. The
 * `(payload)` group already owns `/api/[...slug]`, so a sibling `/api/...`
 * route is a resolution question nobody should have to think about. And an
 * action posts and redirects without any client JavaScript, so the form works
 * on a page that has not hydrated — which is the whole point of a form.
 *
 * Storage is `now_platform`, not the city database: a subscriber is a person
 * and a person can read both cities (see migration 0006).
 */

let platformPool: pg.Pool | null = null

function pool(): pg.Pool {
  const url = process.env.PLATFORM_DATABASE_URI ?? process.env.PLATFORM_DATABASE_URL
  if (!url) throw new Error('PLATFORM_DATABASE_URI is not set')
  platformPool ??= new pg.Pool({ connectionString: url, max: 2, statement_timeout: 5_000 })
  return platformPool
}

/**
 * Deliberately permissive. The only thing worth rejecting here is input that
 * cannot be an address at all — a stricter regex rejects real addresses
 * (plus-tags, new TLDs, unicode locals) and the cost of a wrong rejection is
 * a reader who cannot subscribe and does not know why. Deliverability is
 * proven by the confirmation mail, not by a pattern.
 */
function normalise(raw: string): string | null {
  const email = raw.trim()
  if (email.length < 5 || email.length > 254) return null
  const at = email.indexOf('@')
  if (at < 1 || at !== email.lastIndexOf('@')) return null
  const domain = email.slice(at + 1)
  if (!domain.includes('.') || domain.startsWith('.') || domain.endsWith('.')) return null
  if (/\s/.test(email)) return null
  return email
}

export async function subscribe(formData: FormData): Promise<void> {
  const site = await getSiteConfig()
  const raw = String(formData.get('email') ?? '')
  const source = String(formData.get('source') ?? 'subscribe')

  const email = normalise(raw)
  if (!email) redirect('/subscribe?status=invalid')

  try {
    await pool().query(
      `INSERT INTO engine.newsletter_subscribers (site_slug, email, email_norm, status, source)
       VALUES ($1, $2, lower($2), 'pending', $3)
       ON CONFLICT (site_slug, email_norm) DO NOTHING`,
      [site.slug, email, source.slice(0, 64)],
    )
  } catch {
    // Never surface a database error to a reader as a failed signup they are
    // expected to act on. Tell them plainly that it did not work.
    redirect('/subscribe?status=error')
  }

  // Deliberately the same response whether the row was new or already there.
  // "You are already subscribed" tells an anonymous visitor whether a given
  // address is on the list, which is not theirs to learn.
  redirect('/subscribe?status=ok')
}
