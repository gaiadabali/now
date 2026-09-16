import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { AccountShell, StatusBanner, type StatusMessage } from '@/components/account'
import { SectionRule } from '@/components/primitives'
import { currentReader } from '@/lib/reader'
import { signOut } from '@/lib/readerActions'
import { describePrefs, hasChosen, loadPrefs, loadVocabulary } from '@/lib/preferences'

export const metadata: Metadata = {
  title: 'Your account',
  robots: { index: false, follow: false },
}

export const dynamic = 'force-dynamic'

const STATUS: Record<string, StatusMessage> = {
  password_changed: {
    tone: 'ok',
    head: 'Password updated.',
    body: 'You are signed in with the new one.',
  },
  verified: {
    tone: 'ok',
    head: 'Your email is confirmed.',
    body: 'You are signed in.',
  },
  prefs_saved: {
    tone: 'ok',
    head: 'Saved.',
    body: 'The site will start leaning towards these.',
  },
}

/**
 * The signed-in landing page.
 *
 * The taste profile is the substantial part and is §17's own idea: show the
 * reader what we think they like, and let them fix it. *"Corrections are
 * high-quality training signal."*
 *
 * The rest is named rather than faked. A dashboard of empty placeholder cards
 * reads as broken; a short honest one reads as early.
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
  const status = flag ? STATUS[flag] : undefined

  const [vocabulary, prefs] = await Promise.all([loadVocabulary(), loadPrefs(reader.id)])
  const likes = describePrefs(prefs, vocabulary)
  const chosen = hasChosen(prefs)

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

      <SectionRule label={chosen ? 'We think you like' : 'Tell us what you like'} />
      {chosen ? (
        <>
          <p className="dek" style={{ marginTop: 'var(--space-s)' }}>
            {likes.join(' · ')}
          </p>
          <p className="meta" style={{ marginTop: 'var(--space-2xs)' }}>
            Wrong about any of it? <Link href="/account/preferences">Change it</Link> — being told
            we are wrong is more useful to us than a click.
          </p>
        </>
      ) : (
        <p className="dek" style={{ marginTop: 'var(--space-s)' }}>
          Nothing yet. <Link href="/account/preferences">Pick a few things</Link> and the site
          starts adjusting — it takes about twenty seconds.
        </p>
      )}

      <div style={{ marginTop: 'var(--space-l)' }}>
        <SectionRule label="Coming next" />
        <ul className="dek" style={{ paddingLeft: '1.1em', marginTop: 'var(--space-s)' }}>
          <li>
            <strong>Saved places and articles</strong> — the table is ready; the save button is not
            (E8.6).
          </li>
          <li>
            <strong>What you have been reading</strong> — needs the beacon deployed (E8.5). Until
            then the profile above is everything we know, and all of it is what you told us.
          </li>
          <li>
            <strong>Your itineraries</strong> — waiting on the itinerary API (E5.4).
          </li>
        </ul>
      </div>

      <dl style={{ marginTop: 'var(--space-l)' }}>
        <dt className="kicker">Email</dt>
        <dd className="dek" style={{ margin: 0 }}>
          {reader.email}
          {reader.emailVerified ? null : (
            <>
              {' · '}
              <Link href="/account/verify">confirm it</Link>
            </>
          )}
        </dd>
      </dl>

      <form action={signOut} style={{ marginTop: 'var(--space-l)' }}>
        <button className="signup__btn" type="submit">
          Sign out
        </button>
      </form>
    </AccountShell>
  )
}
