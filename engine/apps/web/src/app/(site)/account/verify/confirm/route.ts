import {
  READER_SESSION_COOKIE,
  READER_SESSION_TTL_SECONDS,
  consumeEmailToken,
  issueReaderToken,
  readerCookieOptions,
} from '@now/auth'
import { NextResponse } from 'next/server'

import { readerSecret, readerStore } from '@/lib/reader'

/**
 * `GET /account/verify/confirm?token=…` — where the verification link lands.
 *
 * A **route handler** rather than a page, because signing the reader in means
 * setting a cookie and Next only permits that from a Server Action or a route
 * handler. The first version of this consumed the token inside the page's
 * render: the verification itself worked and the response was a 500, which is
 * the worst of both — the token spent, the reader shown an error.
 *
 * The human-facing page stays at `/account/verify`, which this redirects to
 * with the outcome. That also keeps the resend form on a URL a reader can
 * return to without a token in hand.
 *
 * **Consuming on GET is deliberate here.** Mail clients and security scanners
 * prefetch links, so a token can be spent before anyone clicks. That is
 * tolerable for verification, where the effect is exactly what the reader
 * wanted anyway. It is NOT tolerable for a reset — a prefetch there would lock
 * someone out of their own recovery — which is why `/account/reset` shows a
 * form and spends its token on POST instead.
 */
export const dynamic = 'force-dynamic'

export async function GET(request: Request): Promise<Response> {
  const token = new URL(request.url).searchParams.get('token')
  const origin = new URL(request.url).origin

  // Every failure — expired, already used, never existed, wrong kind — lands
  // on the same message. Telling someone holding a guessed token which one
  // they hit confirms whether it was ever real.
  const invalid = NextResponse.redirect(`${origin}/account/verify?status=invalid`, 303)
  if (!token) return invalid

  let result
  try {
    result = await consumeEmailToken(readerStore(), token, 'verify_email')
  } catch (error) {
    console.error('[reader] verification failed:', error)
    return NextResponse.redirect(`${origin}/account/verify?status=unavailable`, 303)
  }
  if (!result.ok) return invalid

  await readerStore().markEmailVerified(result.reader.id, new Date())

  // Signed in on success: they have just proven control of the mailbox, and a
  // password prompt here is friction with no security value.
  //
  // Straight to the picker rather than the account page. §17 budgets the whole
  // preference flow at 30 seconds, and the moment someone has just clicked a
  // link to get here is the moment they are most willing to spend twenty of
  // them. Nothing on it is required, so it costs a reader who is not
  // interested exactly one click.
  const response = NextResponse.redirect(`${origin}/account/preferences?status=verified`, 303)
  response.cookies.set(
    READER_SESSION_COOKIE,
    issueReaderToken(
      { identityId: result.reader.id, email: result.reader.email },
      readerSecret(),
    ),
    readerCookieOptions(READER_SESSION_TTL_SECONDS),
  )
  return response
}
