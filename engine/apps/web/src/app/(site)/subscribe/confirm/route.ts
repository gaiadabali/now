import { NextResponse } from 'next/server'

import { confirmSubscription } from '@/lib/newsletter'

/**
 * `GET /subscribe/confirm?token=…` — where the newsletter confirmation lands
 * (E8.1b, closing F135).
 *
 * A route handler rather than a page because it mutates and then redirects,
 * and because `/subscribe` already exists as the human-facing page: the
 * outcome is rendered there, from a status in the URL, exactly like every
 * other state that form can reach.
 *
 * **Consuming on GET is deliberate**, and safe here in a way it is not for a
 * password reset. Mail clients and security scanners prefetch links, so a
 * token can be spent before anyone clicks — for a subscription confirmation
 * the effect of that is precisely what the reader asked for, so a prefetch
 * that "uses it up" has simply done the job early. A reset token spent by a
 * prefetch locks someone out of their own recovery, which is why
 * `/account/reset` shows a form and spends its token on POST instead.
 *
 * No `accountsEnabled()` gate. Confirmation must keep working even if mail is
 * later switched off: a link already sitting in somebody's inbox is a promise
 * that was made when it was sent, and refusing it because the transport has
 * since changed would break that promise for no gain. The subscribe form is
 * gated instead — nothing new is collected that cannot be confirmed.
 */
export const dynamic = 'force-dynamic'

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url)
  const token = url.searchParams.get('token') ?? ''
  const outcome = await confirmSubscription(token)
  // `unavailable` maps to its own status rather than sharing `invalid`'s: a
  // link that failed because our database threw is still a good link, and
  // telling the reader otherwise sends them to ask for a replacement that
  // will fail identically.
  const status = outcome === 'unavailable' ? 'confirm_unavailable' : outcome
  return NextResponse.redirect(`${url.origin}/subscribe?status=${status}`, 303)
}
