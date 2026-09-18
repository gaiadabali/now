import { draftMode } from 'next/headers'
import { redirect } from 'next/navigation'

/**
 * Leave preview.
 *
 * Draft mode is a cookie, so without this an editor who previewed one story
 * keeps seeing unpublished versions of every article they open — including
 * when they later go looking at the live site to check something. That is not
 * a leak (the cookie is theirs and httpOnly), it is worse in a quieter way:
 * they are looking at a page nobody else can see and have no way to tell.
 *
 * The banner on a previewed article links here. No auth check: turning draft
 * mode OFF is safe for anyone to do, and requiring a session to stop
 * previewing would strand someone whose session expired mid-preview in
 * exactly the state this route exists to get them out of.
 */
export async function GET(request: Request) {
  ;(await draftMode()).disable()
  const to = new URL(request.url).searchParams.get('to')
  // Same-origin, single-segment paths only. `to` comes off the URL, and an
  // open redirect on a route that anyone may call is how a phishing link gets
  // to borrow this domain's good name.
  redirect(to && /^\/[A-Za-z0-9-]*$/.test(to) ? to : '/')
}
