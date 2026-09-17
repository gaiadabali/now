import 'server-only'

import { Mailer, createTransportFromEnv } from '@now/mailer'

import { getSiteConfig } from '@/lib/site'

/**
 * The one place that answers "can this deployment send email at all?"
 *
 * Extracted from `lib/reader.ts` when the newsletter needed the same answer
 * (E8.1b). Two surfaces depend on mail — the account flow and the newsletter's
 * double opt-in — and both of them fail the same way without it: not by
 * erroring, but by **succeeding wrongly**. The account form created a real
 * credential and said "check your email" (F141). The subscribe form still
 * writes a `pending` row and says "You are on the list… the next edition will
 * arrive on schedule" (F135). Neither is true, and neither shows any sign of
 * being untrue to the person it is untrue about.
 *
 * Derived rather than a flag somebody has to remember to flip, so it is right
 * by default and self-heals the moment SMTP is configured.
 */
export function mailConfigured(): boolean {
  return createTransportFromEnv().ok
}

let mailer: Mailer | null = null

/**
 * The shared sender.
 *
 * Throws when the transport cannot be built — deliberately. Every caller is
 * expected to have checked `mailConfigured()` first; reaching here without it
 * is a bug, and returning a no-op mailer would hide exactly the class of
 * failure this module exists to stop.
 */
export function sharedMailer(): Mailer {
  if (mailer) return mailer
  const selected = createTransportFromEnv()
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

/**
 * The origin links in email point at.
 *
 * From configuration — `SITE_BASE_URL`, falling back to the site config's own
 * hostname — and **never** from a request `Host` header, which is
 * host-header injection (see `packages/mailer/src/links.ts`).
 *
 * ⚠️ The fallback is not safe to rely on today. `sites.hostname` holds the
 * POST-CUTOVER hostname, which on production is the legacy WordPress site on a
 * different server (F142) — so an unset `SITE_BASE_URL` produces links that
 * point somewhere real and entirely wrong. DEPLOY.md lists it as a
 * precondition of turning either mail surface on.
 */
export async function siteBaseUrl(): Promise<string> {
  const configured = process.env.SITE_BASE_URL
  if (configured) return configured
  const site = await getSiteConfig()
  return `https://${site.hostname}`
}

export function allowInsecureLinks(): boolean {
  return process.env.NODE_ENV !== 'production'
}
