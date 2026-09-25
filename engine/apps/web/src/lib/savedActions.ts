'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'

import { safeInternalPath } from '@/lib/internalPath'
import { currentReader } from '@/lib/reader'
import { saveArticle, unsaveArticle } from '@/lib/savedItems'

/**
 * The Save/Saved toggle's write path — `components/SaveButton.tsx` (the
 * article page's share rail) and the dashboard's Saved panel both post here.
 *
 * One action for both directions rather than a `save`/`unsave` pair: the
 * form that calls it already knows which way it is toggling (it rendered
 * from the current, server-known state), so there is nothing to read back
 * before deciding, and no window for two concurrent submits to disagree
 * about which direction "toggle" means.
 *
 * A server action, not a route handler — no client JavaScript hydrates this
 * control, matching every other reader form in `lib/readerActions.ts`.
 */

function field(form: FormData, name: string): string {
  const value = form.get(name)
  return typeof value === 'string' ? value : ''
}

export async function toggleSaved(form: FormData): Promise<void> {
  // `returnTo` is only ever used for the SIGNED-OUT branch below now (a
  // real cross-page redirect, to sign-in). The success path used to
  // `redirect(returnTo)` as well — back to the very page the form was
  // rendered on — and that was the bug found live while driving this with
  // Playwright: the article page's own Save button kept reading "Save"
  // after a successful click, and the dashboard's "Remove from saved" kept
  // the removed item on screen, both while `psql` showed the write had
  // genuinely landed. A `redirect()` back to the CURRENT page is still a
  // navigation as far as Next's client Router Cache is concerned, and it
  // served the segment it had already cached from the page the reader was
  // just looking at — `revalidatePath` alone did not stop that (confirmed
  // with a hard reload showing the correct state immediately, a soft one
  // not). The fix is to not navigate at all: no `redirect()` on success,
  // just the write plus `revalidatePath` for wherever it is visible. A
  // server action's response IS how Next refreshes the page that called
  // it — that is the documented shape (a "like button" is the canonical
  // example), and it sidesteps the Router Cache entirely because there is
  // no navigation for it to have an opinion about.
  const returnTo = safeInternalPath(field(form, 'returnTo')) ?? '/account'
  // `revalidatePath` wants a path, not a `#fragment` — `returnTo` may carry
  // one (the article page no longer needs it now that nothing navigates,
  // but old links/bookmarks could still include it).
  const pathOnly = returnTo.split('#')[0]

  const reader = await currentReader()
  if (!reader) {
    // Can happen if a session expires between the page rendering the button
    // and the click reaching the server — not just a hostile hand-post. This
    // IS a real cross-page redirect, to a path that was not just rendered,
    // so the Router Cache trap above does not apply here.
    redirect(`/account/login?next=${encodeURIComponent(returnTo)}`)
  }

  const entityId = field(form, 'entityId')
  if (entityId) {
    if (field(form, 'intent') === 'unsave') {
      await unsaveArticle(reader.id, entityId)
    } else {
      await saveArticle(reader.id, entityId)
    }
  }

  // `/account` unconditionally, not only when it IS `pathOnly`: the
  // dashboard's Saved (and Picked for you, which weighs a save at 1.0)
  // panels need to reflect a save made from ANY article page, not only one
  // toggled while the dashboard itself was open.
  revalidatePath(pathOnly)
  revalidatePath('/account')
}
