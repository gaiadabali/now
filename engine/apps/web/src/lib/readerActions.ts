'use server'

import {
  READER_SESSION_COOKIE,
  READER_SESSION_TTL_SECONDS,
  RESET_TOKEN_TTL_HOURS,
  VERIFY_TOKEN_TTL_HOURS,
  authenticateReader,
  completePasswordReset,
  consumeEmailToken,
  issueEmailToken,
  issueReaderToken,
  normaliseReaderEmail,
  readerCookieClearOptions,
  readerCookieOptions,
  registerReader,
} from '@now/auth'
import { buildLink, resetPassword, verifyEmail } from '@now/mailer'
import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

import {
  accountsEnabled,
  allowInsecureLinks,
  currentReader,
  mailBranding,
  readerMailer,
  readerSecret,
  readerStore,
  siteBaseUrl,
} from '@/lib/reader'
import { savePrefs } from '@/lib/preferences'
import { rateLimit } from '@/lib/rateLimit'
import { stitchAnonymousHistory } from '@/lib/stitch'

/**
 * Register, sign in, sign out, verify, reset (E8.3).
 *
 * Server actions rather than route handlers, following `lib/newsletter.ts`:
 * the `(payload)` group already owns `/api/[...slug]`, and an action posts and
 * redirects with no client JavaScript, so these forms work on a page that has
 * not hydrated. Every outcome is a real, linkable URL.
 *
 * ## The rule that shapes all of it
 *
 * **No response here may reveal whether an address has an account.** Register,
 * sign-in and forgot-password all answer identically for a known and an
 * unknown address. That costs a little clarity for legitimate users — "did I
 * already sign up?" is answered by email, not on screen — and it is the
 * difference between a login form and an address-validation service for
 * whoever is testing a breach list against it.
 */

// Rate limiting moved to `lib/rateLimit.ts` (E8.3a): Redis-backed so the
// budget is shared across containers and survives a redeploy, with a logged
// in-process fallback when Redis is unreachable.

function field(form: FormData, name: string): string {
  const value = form.get(name)
  return typeof value === 'string' ? value : ''
}

// --- registration ----------------------------------------------------------

export async function register(form: FormData): Promise<void> {
  const email = field(form, 'email')
  const password = field(form, 'password')
  const name = field(form, 'name')
  const emailNorm = normaliseReaderEmail(email)

  if (!(await rateLimit(`register:${emailNorm}`, 5, 60 * 60_000))) {
    redirect('/account/register?status=slow_down')
  }

  // Checked BEFORE any row is created. A misconfigured base URL is a
  // deployment error that affects everyone equally, and discovering it after
  // the insert leaves an account nobody can verify and a visitor looking at a
  // 500 — which is exactly what happened the first time this ran.
  // Checked BEFORE any row is created — both of them.
  //
  // The link check was already here. The mail check was NOT, and that was the
  // bug that reached production (F141): `sendVerification` swallows failures so
  // a transient bounce does not cost someone their registration, which is right
  // when mail usually works. When mail is not configured AT ALL it is exactly
  // wrong — every sign-up creates a real account with a real password hash,
  // tells the person to check their inbox, and sends nothing. They cannot
  // verify, cannot reset, and are given no sign that anything failed.
  //
  // "Cannot send at all" is a deployment error affecting everyone equally, so
  // saying so plainly reveals nothing about any address.
  if (!accountsEnabled() || !(await linkConfigUsable())) {
    redirect('/account/register?status=unavailable')
  }

  const store = readerStore()
  const result = await registerReader(store, { email, password, name })

  if (!result.ok && result.reason === 'invalid_email') {
    redirect('/account/register?status=invalid_email')
  }
  if (!result.ok && result.reason === 'weak_password') {
    redirect(`/account/register?status=weak_password&why=${result.detail ?? 'too_short'}`)
  }

  // `already_registered` deliberately falls through to the SAME destination as
  // success. The person who owns the address learns about it in their inbox;
  // whoever typed it learns nothing.
  if (result.ok) {
    await sendVerification(result.reader.id, result.reader.email)
  }
  // Nothing is sent to an existing account here — a "you already have an
  // account" mail is the right courtesy but it is also an unsolicited mail
  // triggerable by anyone who knows the address, so it needs its own rate
  // limit. Tracked, not faked.

  redirect('/account/register?status=check_email')
}

/** Is the link origin configured well enough to build a usable link at all? */
async function linkConfigUsable(): Promise<boolean> {
  return buildLink(
    await siteBaseUrl(),
    '/account/verify',
    { token: 'probe' },
    { allowInsecure: allowInsecureLinks() },
  ).ok
}

/**
 * Sends the verification mail. Never throws.
 *
 * A delivery failure must not cost the reader their registration — the account
 * exists and is usable, and `/account/verify` can issue another link. The
 * caller deliberately does **not** surface the difference: a "we could not
 * send mail" message would appear only for addresses that are genuinely new,
 * which would turn the registration form back into the enumeration oracle the
 * rest of this file is careful to avoid.
 */
async function sendVerification(identityId: string, email: string): Promise<boolean> {
  try {
    const store = readerStore()
    const { secret } = await issueEmailToken(store, identityId, 'verify_email')
    const link = buildLink(
      await siteBaseUrl(),
      '/account/verify/confirm',
      { token: secret },
      { allowInsecure: allowInsecureLinks() },
    )
    if (!link.ok) {
      console.error(`[reader] cannot build verification link: ${link.reason}`)
      return false
    }

    const branding = await mailBranding()
    const sent = await readerMailer().send({
      to: { email },
      ...verifyEmail(branding, link.url, VERIFY_TOKEN_TTL_HOURS),
      tag: 'verify_email',
    })
    // Logged without the address: a failed send is an operational signal, not
    // a reason to write someone's email into the log stream.
    if (!sent.ok) console.error(`[reader] verification mail failed: ${sent.reason}`)
    return sent.ok
  } catch (error) {
    console.error('[reader] verification mail threw:', error)
    return false
  }
}

// --- sign in / out ---------------------------------------------------------

export async function signIn(form: FormData): Promise<void> {
  const email = field(form, 'email')
  const password = field(form, 'password')
  const emailNorm = normaliseReaderEmail(email)

  if (!(await rateLimit(`login:${emailNorm}`, 15, 15 * 60_000))) {
    redirect('/account/login?status=slow_down')
  }

  const result = await authenticateReader(readerStore(), email, password)

  if (!result.ok) {
    // `locked` and `suspended` are distinguishable from `invalid_credentials`
    // on purpose: both are only reachable AFTER a correct identification, so
    // neither reveals whether an address exists, and both are actionable by
    // the legitimate owner who would otherwise keep retrying a password that
    // is in fact correct.
    const status =
      result.reason === 'locked' ? 'locked' : result.reason === 'suspended' ? 'suspended' : 'invalid'
    redirect(`/account/login?status=${status}`)
  }

  await establishSession(result.reader.id, result.reader.email)
  redirect('/account')
}

async function establishSession(identityId: string, email: string): Promise<void> {
  const token = issueReaderToken({ identityId, email }, readerSecret())
  const jar = await cookies()
  jar.set(READER_SESSION_COOKIE, token, readerCookieOptions(READER_SESSION_TTL_SECONDS))

  // Claim this device's recent anonymous reading, so a reader who browsed for
  // weeks before signing up does not start from zero (E8.5). Bounded and
  // never throws — see lib/stitch.ts for why both matter.
  await stitchAnonymousHistory(identityId)
}

export async function signOut(): Promise<void> {
  const jar = await cookies()
  // Cleared with identical attributes and maxAge 0 — a Set-Cookie that differs
  // in path or Secure does not replace the original, it sits beside it.
  jar.set(READER_SESSION_COOKIE, '', readerCookieClearOptions())
  redirect('/account/login?status=signed_out')
}

// --- verification ----------------------------------------------------------

export async function resendVerification(form: FormData): Promise<void> {
  const email = normaliseReaderEmail(field(form, 'email'))
  if (!(await rateLimit(`resend:${email}`, 3, 60 * 60_000))) {
    redirect('/account/verify?status=slow_down')
  }
  const reader = await readerStore().findByEmail(email)
  if (reader && reader.status === 'active' && !reader.emailVerifiedAt) {
    await sendVerification(reader.id, reader.email)
  }
  redirect('/account/verify?status=resent')
}

// --- password reset --------------------------------------------------------

export async function requestReset(form: FormData): Promise<void> {
  const email = field(form, 'email')
  const emailNorm = normaliseReaderEmail(email)

  // Tighter than sign-in: each request sends mail to an address the requester
  // may not own, so the limit protects a third party's inbox, not just us.
  if (!(await rateLimit(`reset:${emailNorm}`, 3, 60 * 60_000))) {
    redirect('/account/forgot?status=sent')
  }
  // A reset that cannot be mailed is a reset that cannot happen. Answering
  // "check your email" anyway would be the same lie registration was telling.
  if (!accountsEnabled()) {
    redirect('/account/forgot?status=unavailable')
  }

  const store = readerStore()
  const reader = await store.findByEmail(emailNorm)

  if (reader && reader.status === 'active') {
    const { secret } = await issueEmailToken(store, reader.id, 'reset_password')
    const link = buildLink(
      await siteBaseUrl(),
      '/account/reset',
      { token: secret },
      { allowInsecure: allowInsecureLinks() },
    )
    if (link.ok) {
      const branding = await mailBranding()
      await readerMailer().send({
        to: { email: reader.email },
        ...resetPassword(branding, link.url, RESET_TOKEN_TTL_HOURS),
        tag: 'reset_password',
      })
    }
  }

  // Always the same page, whether or not anything was sent. This is the
  // single most common place an enumeration oracle is left open.
  redirect('/account/forgot?status=sent')
}

export async function completeReset(form: FormData): Promise<void> {
  const token = field(form, 'token')
  const password = field(form, 'password')

  const store = readerStore()
  const result = await consumeEmailToken(store, token, 'reset_password')
  if (!result.ok) redirect('/account/reset?status=invalid')

  const changed = await completePasswordReset(store, result.reader.id, password)
  if (!changed.ok) {
    // The token was consumed by the check above, so a weak password would
    // otherwise strand the reader with a dead link. Issue a fresh one and
    // keep them in the flow.
    const { secret } = await issueEmailToken(store, result.reader.id, 'reset_password')
    redirect(`/account/reset?token=${encodeURIComponent(secret)}&status=weak&why=${changed.reason}`)
  }

  await establishSession(result.reader.id, result.reader.email)
  redirect('/account?status=password_changed')
}

// --- preferences (E8.4) ----------------------------------------------------

/**
 * Saves the §17 picker.
 *
 * Multi-select arrives as repeated checkbox values, which `FormData.getAll`
 * gives us directly — no client JavaScript anywhere in this flow, so the
 * picker works on a page that has not hydrated, exactly like the rest of the
 * account forms.
 *
 * Validation against the live vocabulary happens in `savePrefs`, not here: a
 * hand-posted form must not be able to write a slug the taxonomy does not
 * have, and putting that check next to the write means every caller gets it.
 */
export async function savePreferences(form: FormData): Promise<void> {
  const reader = await currentReader()
  if (!reader) redirect('/account/login')

  const list = (name: string): string[] =>
    form.getAll(name).filter((v): v is string => typeof v === 'string' && v.length > 0)
  const one = (name: string): string | null => {
    const value = form.get(name)
    return typeof value === 'string' && value.length > 0 ? value : null
  }

  await savePrefs(reader.id, {
    interests: list('interests'),
    topics: list('topics'),
    areas: list('areas'),
    persona: one('persona'),
    budget: one('budget'),
  })

  redirect('/account?status=prefs_saved')
}
