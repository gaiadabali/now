import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { AccountShell, StatusBanner, type StatusMessage } from '@/components/account'
import { SectionRule } from '@/components/primitives'
import { currentReader } from '@/lib/reader'
import { signOut } from '@/lib/readerActions'

export const metadata: Metadata = {
  title: 'Your account',
  robots: { index: false, follow: false },
}

export const dynamic = 'force-dynamic'

/**
 * The signed-in landing page.
 *
 * Deliberately thin — the real dashboard is E8.6 and needs E8.4's preference
 * picker and E8.5's deployed beacon before it has anything to show. What is
 * here is what exists today: who you are, whether your address is confirmed,
 * and a way out. Panels are named rather than faked, because a dashboard of
 * empty placeholder cards reads as broken, while a short honest one reads as
 * early.
 */
export default async function AccountPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}) {
  const reader = await currentReader()
  if (!reader) redirect('/account/login')

  const query = (await searchParams) ?? {}
  const flag = typeof query.status === 'string' ? query.status : undefined
  const status: StatusMessage | undefined =
    flag === 'password_changed'
      ? { tone: 'ok', head: 'Password updated.', body: 'You are signed in with the new one.' }
      : flag === 'verified'
        ? {
            tone: 'ok',
            head: 'Your email is confirmed.',
            body: 'You are signed in. Tell us what you are into and the site starts adjusting to it.',
          }
        : undefined

  return (
    <AccountShell
      kicker="Your account"
      title={reader.name ? `Hello, ${reader.name}.` : 'Your account'}
      status={status}
    >
      {!reader.emailVerified ? (
        <StatusBanner
          status={{
            tone: 'info',
            head: 'Your email is not confirmed yet.',
            body: 'You can use the site as normal. Confirming it lets us send you the things you ask for.',
          }}
        />
      ) : null}

      <dl style={{ margin: 0 }}>
        <dt className="kicker">Email</dt>
        <dd className="dek" style={{ margin: '0 0 var(--space-m)' }}>
          {reader.email}
          {reader.emailVerified ? null : (
            <>
              {' · '}
              <Link href="/account/verify">confirm it</Link>
            </>
          )}
        </dd>
      </dl>

      <SectionRule label="Coming next" />
      <ul className="dek" style={{ paddingLeft: '1.1em', marginTop: 'var(--space-s)' }}>
        <li>
          <strong>What you are into</strong> — pick your topics and areas, and the site starts
          adjusting to them (E8.4).
        </li>
        <li>
          <strong>Saved places and articles</strong> — the table is ready; the save button is not
          (E8.6).
        </li>
        <li>
          <strong>What you have been reading</strong> — needs the beacon deployed (E8.5).
        </li>
        <li>
          <strong>Your itineraries</strong> — waiting on the itinerary API (E5.4).
        </li>
      </ul>

      <form action={signOut} style={{ marginTop: 'var(--space-l)' }}>
        <button className="signup__btn" type="submit">
          Sign out
        </button>
      </form>
    </AccountShell>
  )
}
