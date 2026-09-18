import { draftMode } from 'next/headers'
import { redirect } from 'next/navigation'

import { canReadEditorial, currentUser } from '@/lib/auth'
import { payloadClient } from '@/lib/payload'
import { slugFromPermalink } from '@/lib/payload'

/**
 * Preview — the draft-mode plumbing the CMS has been waiting on (S4).
 *
 * The body editor's own header comment named this as the missing piece:
 * *"Payload's own live preview puts the real route in an iframe and is the
 * better answer eventually; it needs draft-mode plumbing through the public
 * site."* This is that plumbing. It was blocked on something else first —
 * until S1.1 an unpublished article had no address to preview it at.
 *
 * `GET /preview?collection=articles&id=123` verifies the visitor is staff,
 * enables Next's draft mode for their browser, and redirects to the story at
 * its real URL, rendered by the real layout. What an editor sees is the page,
 * not an approximation of it.
 *
 * **Why the staff session and not a signed token in the URL.** The admin is
 * served by this same app on this same origin
 * (docs/ADMIN-CONSOLIDATION.md Phase 2), so the Payload session cookie is
 * already on this request and `payload.auth()` is the same check every
 * `/team-editor` page makes. A token in a query string is a bearer credential
 * that lands in browser history, in any analytics that records URLs, and in
 * whatever an editor pastes into chat to say "look at this". There is nothing
 * for a token to buy here, so there is no token.
 *
 * **What draft mode does and does not open up.** It sets an httpOnly cookie
 * that makes `[slug]` ask for the newest version instead of the published
 * one — for that browser only. It cannot be enabled by asking for it: this
 * route is the only thing that calls `enable()`, and it refuses anyone
 * without an editorial role. A reader who has never been through here sees
 * published content at every URL, which is why `getBySlug` defaults `draft`
 * to false rather than reading the cookie itself.
 */
export async function GET(request: Request) {
  const url = new URL(request.url)
  const collection = url.searchParams.get('collection')
  const id = url.searchParams.get('id')

  // Identical response for "not signed in" and "signed in without an
  // editorial role", so this route cannot be used to probe who has one.
  const user = await currentUser()
  if (!user || !canReadEditorial(user)) {
    return new Response('Not found', { status: 404 })
  }

  // Only articles today. Places and Events have public pages too, but their
  // drafts are not what anyone asked to preview, and an allowlist beats a
  // pass-through the day someone adds a collection with no public route.
  if (collection !== 'articles' || !id) {
    return new Response('Preview is available for articles.', { status: 400 })
  }

  const payload = await payloadClient()
  let doc: Record<string, unknown> | null = null
  try {
    doc = (await payload.findByID({
      collection: 'articles',
      id,
      draft: true,
      depth: 0,
      overrideAccess: false,
      user,
    })) as Record<string, unknown>
  } catch {
    // findByID throws on a missing id, and on one this user may not read.
    return new Response('Not found', { status: 404 })
  }

  // The address to preview at, newest first — the same precedence
  // `getBySlug` resolves by, so preview and publication cannot disagree about
  // where a story lives.
  const slug =
    (typeof doc.slug === 'string' && doc.slug !== '' ? doc.slug : null) ??
    slugFromPermalink(doc.legacyPermalink as string | null)

  if (!slug) {
    // Reachable only for a draft whose title slugified to nothing, which the
    // slug field's `required` normally prevents at publish time.
    return new Response('This draft has no web address yet — set one on the Story tab.', { status: 409 })
  }

  ;(await draftMode()).enable()
  redirect(`/${slug}`)
}
