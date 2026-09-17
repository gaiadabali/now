'use server'

import { buildLink, newsletterConfirm } from '@now/mailer'
import crypto from 'node:crypto'
import { redirect } from 'next/navigation'
import pg from 'pg'

import { allowInsecureLinks, mailBranding, mailConfigured, sharedMailer, siteBaseUrl } from '@/lib/mail'
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

/** Hours a confirmation link stays good. Longer than a password reset — this
 *  one sits in an inbox until someone next checks their mail, and nothing is
 *  at stake if it is opened late. */
const CONFIRM_TTL_HOURS = 72

/** Only the digest is stored; the secret rides in the link (migration 0010). */
function newToken(): { secret: string; hash: string } {
  const secret = crypto.randomBytes(32).toString('base64url')
  return { secret, hash: crypto.createHash('sha256').update(secret).digest('hex') }
}

export async function subscribe(formData: FormData): Promise<void> {
  const site = await getSiteConfig()
  const raw = String(formData.get('email') ?? '')
  const source = String(formData.get('source') ?? 'subscribe')

  const email = normalise(raw)
  if (!email) redirect('/subscribe?status=invalid_email')

  // Checked BEFORE the row is written. Without mail there is no way to confirm,
  // so a signup cannot complete — and storing the address anyway while saying
  // "you are on the list" is the wrong-success shape F141 shipped on the
  // account form. Nothing is collected that cannot be acted on.
  if (!mailConfigured()) redirect('/subscribe?status=unavailable')

  const { secret, hash } = newToken()
  const expires = new Date(Date.now() + CONFIRM_TTL_HOURS * 3_600_000)

  try {
    // A repeat signup REFRESHES the token rather than doing nothing. Someone
    // re-submitting the form is usually someone whose first link never arrived
    // or has lapsed, and the old behaviour — ON CONFLICT DO NOTHING — left them
    // permanently unable to confirm, with the page cheerfully saying it worked.
    //
    // Confirmed rows are left alone: re-subscribing must not silently reopen a
    // confirmation someone already completed, and must not unconfirm them.
    await pool().query(
      `INSERT INTO engine.newsletter_subscribers
             (site_slug, email, email_norm, status, source,
              confirm_token_hash, confirm_expires_at, confirm_sent_at)
       VALUES ($1, $2, lower($2), 'pending', $3, $4, $5, now())
       ON CONFLICT (site_slug, email_norm) DO UPDATE
          SET confirm_token_hash = EXCLUDED.confirm_token_hash,
              confirm_expires_at = EXCLUDED.confirm_expires_at,
              confirm_sent_at    = now()
        WHERE engine.newsletter_subscribers.status = 'pending'`,
      [site.slug, email, source.slice(0, 64), hash, expires],
    )
  } catch {
    redirect('/subscribe?status=error')
  }

  const link = buildLink(
    await siteBaseUrl(),
    '/subscribe/confirm',
    { token: secret },
    { allowInsecure: allowInsecureLinks() },
  )
  if (link.ok) {
    try {
      const sent = await sharedMailer().send({
        to: { email },
        ...newsletterConfirm(await mailBranding(), link.url),
        tag: 'newsletter_confirm',
      })
      // Logged without the address — an operational signal, not a reason to
      // write someone's email into the log stream.
      if (!sent.ok) console.error(`[newsletter] confirmation mail failed: ${sent.reason}`)
    } catch (error) {
      console.error('[newsletter] confirmation mail threw:', error)
    }
  } else {
    console.error(`[newsletter] cannot build confirmation link: ${link.reason}`)
  }

  // The same response whether the row was new, refreshed, or already confirmed.
  // "You are already subscribed" tells an anonymous visitor whether a given
  // address is on the list, which is not theirs to learn.
  redirect('/subscribe?status=check_email')
}

export type ConfirmOutcome = 'confirmed' | 'invalid'

/**
 * Redeems a confirmation token exactly once.
 *
 * Every failure — lapsed, already used, never existed — collapses to
 * `invalid`. Distinguishing them would tell someone holding a guessed token
 * whether they had guessed a real one.
 */
export async function confirmSubscription(secret: string): Promise<ConfirmOutcome> {
  if (!secret) return 'invalid'
  const hash = crypto.createHash('sha256').update(secret).digest('hex')
  try {
    // One statement, so two clicks on the same link cannot both confirm: the
    // second finds no row whose token is still live. Clearing the hash is what
    // makes it single-use.
    const { rowCount } = await pool().query(
      `UPDATE engine.newsletter_subscribers
          SET status = 'confirmed',
              confirmed_at = COALESCE(confirmed_at, now()),
              confirm_token_hash = NULL,
              confirm_expires_at = NULL
        WHERE confirm_token_hash = $1
          AND status = 'pending'
          AND confirm_expires_at > now()`,
      [hash],
    )
    return rowCount === 1 ? 'confirmed' : 'invalid'
  } catch (error) {
    console.error('[newsletter] confirmation failed:', error)
    return 'invalid'
  }
}
