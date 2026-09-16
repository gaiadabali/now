import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import Link from 'next/link'

import { AccountShell, Field, Submit, type StatusMessage } from '@/components/account'
import { MIN_PASSWORD_LENGTH } from '@now/auth'
import { completeReset } from '@/lib/readerActions'
import { accountsEnabled } from '@/lib/reader'

export const metadata: Metadata = {
  title: 'Set a new password',
  robots: { index: false, follow: false },
}

/**
 * Where a reset link lands.
 *
 * Unlike `/account/verify`, the token is **not** consumed on render. Mail
 * clients and security scanners prefetch links, and a prefetched reset would
 * burn the token before the reader ever saw the form — locking them out of
 * their own recovery with a link that now says it is invalid. So this page
 * only displays; the token rides in a hidden field and is spent on POST.
 */
export const dynamic = 'force-dynamic'

const WEAK: Record<string, string> = {
  too_short: `Use at least ${MIN_PASSWORD_LENGTH} characters.`,
  too_long: 'That is longer than we can accept — trim it a little.',
  too_common: 'That one appears in every breach list there is. Pick something less guessable.',
}

export default async function ResetPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}) {
  // The whole surface is unreachable when mail is not configured — a form that
  // cannot complete is worse than no form (F141). notFound(), not a message:
  // an explanation would invite people to keep trying.
  if (!accountsEnabled()) notFound()
  const query = (await searchParams) ?? {}
  const token = typeof query.token === 'string' ? query.token : ''
  const flag = typeof query.status === 'string' ? query.status : undefined
  const why = typeof query.why === 'string' ? query.why : 'too_short'

  let status: StatusMessage | undefined
  if (flag === 'invalid') {
    status = {
      tone: 'bad',
      head: 'That link is no longer valid.',
      body: 'Reset links last an hour and work once. Ask for a new one and try again.',
    }
  } else if (flag === 'weak') {
    status = {
      tone: 'bad',
      head: 'Pick a stronger password.',
      body: `${WEAK[why] ?? WEAK.too_short} Your link is still good — try again below.`,
    }
  }

  const usable = token.length > 0 && flag !== 'invalid'

  return (
    <AccountShell
      kicker="Your account"
      title="Set a new password."
      status={status}
      footer={
        usable ? undefined : (
          <>
            <Link href="/account/forgot">Ask for a new reset link</Link>.
          </>
        )
      }
    >
      {usable ? (
        <form action={completeReset}>
          <input type="hidden" name="token" value={token} />
          <Field
            id="password"
            name="password"
            label="New password"
            type="password"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD_LENGTH}
            hint={`At least ${MIN_PASSWORD_LENGTH} characters. A phrase you can remember beats a short tangle of symbols.`}
          />
          <Submit>Save new password</Submit>
        </form>
      ) : null}
    </AccountShell>
  )
}
