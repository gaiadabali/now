import Link from 'next/link'

import { toggleSaved } from '@/lib/savedActions'

/**
 * The Save/Saved toggle — the article page's share rail (DESIGN-SYSTEM.md §3
 * flagged this exact gap: "A Save affordance with no persistence behind it
 * … leaves Save to whoever wires the write path"). `lib/savedItems.ts` is
 * that write path; this is the one control that calls it.
 *
 * Three states, not two:
 *
 * - Accounts unreachable (`accountsEnabled()` false, F141 — no mail
 *   transport configured) — renders nothing. The site must never show a
 *   control that leads to a 404, and every `/account/*` route 404s in this
 *   state.
 * - Signed out — a plain link to sign in, carrying `next` so the reader
 *   comes straight back to this article rather than landing on the
 *   dashboard after proving who they are. Not a form: there is no session
 *   yet to attach a save to, so there is nothing to submit.
 * - Signed in — a real toggle, `aria-pressed` tied to the actual saved
 *   state (read server-side, not guessed), posting to the one server
 *   action that writes both directions (`lib/savedActions.ts`).
 *
 * Zero client JavaScript, matching every other reader-facing form on this
 * site (`lib/readerActions.ts`'s own doc comment): a submit reaches the
 * server action, which does the write and calls `revalidatePath` —
 * deliberately NOT a `redirect()` back to this same page (see
 * `lib/savedActions.ts` for the Router Cache trap that was). Next
 * refreshes this component in place from the action's own response, so the
 * toggle's new state is what the write actually produced, not an
 * optimistic client guess.
 */
export function SaveButton({
  articleId,
  articlePath,
  saved,
  accountsEnabled,
  signedIn,
}: {
  articleId: number
  /** e.g. `/some-article-slug` — used both as the post-toggle redirect
   * target and, signed out, as the sign-in flow's own return path. */
  articlePath: string
  saved: boolean
  accountsEnabled: boolean
  signedIn: boolean
}) {
  if (!accountsEnabled) return null

  if (!signedIn) {
    return (
      <Link className="share__save" href={`/account/login?next=${encodeURIComponent(articlePath)}`}>
        Save <span aria-hidden="true">↗</span>
      </Link>
    )
  }

  return (
    <form action={toggleSaved}>
      <input type="hidden" name="entityId" value={articleId} />
      <input type="hidden" name="intent" value={saved ? 'unsave' : 'save'} />
      <input type="hidden" name="returnTo" value={articlePath} />
      <button className="share__save" type="submit" aria-pressed={saved}>
        {saved ? 'Saved' : 'Save'} <span aria-hidden="true">{saved ? '✓' : '+'}</span>
      </button>
    </form>
  )
}
