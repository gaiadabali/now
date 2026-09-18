import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect, notFound } from 'next/navigation'

import { AccountShell, EmptyState, Panel, StatusBanner, type StatusMessage } from '@/components/account'
import { currentReader, accountsEnabled } from '@/lib/reader'
import { signOut } from '@/lib/readerActions'
import { describePrefs, hasChosen, loadPrefs, loadVocabulary } from '@/lib/preferences'
import { getSiteConfig } from '@/lib/site'

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

/** "Good morning/afternoon/evening" — the site's own clock, not the reader's device. */
function partOfDay(timezone: string): string {
  const hour = Number(
    new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hourCycle: 'h23', timeZone: timezone }).format(
      new Date(),
    ),
  )
  if (hour < 5) return 'evening' // late night reads as "evening" rather than "morning"
  if (hour < 12) return 'morning'
  if (hour < 17) return 'afternoon'
  return 'evening'
}

/**
 * The reader's own page inside the magazine (§4).
 *
 * Kept inside `(site)` deliberately — masthead, nav and edition line all
 * carry through, because this is a department of the magazine, not a
 * separate console. The admin surfaces drop all three; this is the one
 * reader-facing screen that is not one of them.
 *
 * Four of six panels have nothing to show yet, and that is not a bug to hide:
 * §4 is explicit that a panel whose data does not exist still renders, with
 * an invitation, because a reader cannot otherwise tell "not built" apart
 * from "you have none". The alternative — four blank boxes, or hiding them
 * outright — is the exact failure a new reader would land on, since a
 * brand-new account is every one of these states at once.
 */
export default async function AccountPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}) {
  // The whole surface is unreachable when mail is not configured — a form that
  // cannot complete is worse than no form (F141). notFound(), not a message:
  // an explanation would invite people to keep trying.
  if (!accountsEnabled()) notFound()
  const reader = await currentReader()
  if (!reader) redirect('/account/login')

  const query = (await searchParams) ?? {}
  const flag = typeof query.status === 'string' ? query.status : undefined
  const status = flag ? STATUS[flag] : undefined

  const [vocabulary, prefs, site] = await Promise.all([
    loadVocabulary(),
    loadPrefs(reader.id),
    getSiteConfig(),
  ])
  const likes = describePrefs(prefs, vocabulary)
  const chosen = hasChosen(prefs)

  const part = partOfDay(site.timezone)
  // Reader.name is optional at registration (Field's own hint says so), and a
  // blank greeting reads better than a guessed one — "Good evening." rather
  // than "Good evening, there."
  const greeting = reader.name ? `Good ${part}, ${reader.name}.` : `Good ${part}.`

  return (
    <>
      <section className="acct-greeting">
        <div className="shell acct-greeting__row">
          <h1 className="acct-greeting__hello">{greeting}</h1>
          {/* No "Reader since {month}" clause: `ReaderRecord` (engine/packages/auth)
              does not expose `identities.created_at`, and a join date is not
              something to guess at. Flagged in the handback as a follow-up —
              adding one column to the store's SELECT is a backend change, and
              packages/auth is outside this task's file ownership. */}
          {/* "Reader since March 2026 · <this city>'s edition". The join date
              was left out of the first build because the reader store did not
              select `identities.created_at` — the column has existed since
              platform baseline 0001, so the fix was the SELECT rather than a
              migration. Still conditional: a store is not obliged to supply
              it, and a greeting is the last place to print a guessed date. */}
          <p className="acct-greeting__meta">
            {reader.joinedAt
              ? `Reader since ${new Intl.DateTimeFormat(site.locale, {
                  month: 'long',
                  year: 'numeric',
                  timeZone: site.timezone,
                }).format(reader.joinedAt)} · ${site.name} edition`
              : `${site.name} edition`}
          </p>
        </div>
      </section>

      {status || !reader.emailVerified ? (
        <div className="shell acct-notices">
          {status ? <StatusBanner status={status} /> : null}
          {!reader.emailVerified ? (
            <StatusBanner
              status={{
                tone: 'info',
                head: 'Your email is not confirmed yet.',
                body: 'You can use the site as normal. Confirming it lets us send you the things you ask for — resend the link from your account page.',
              }}
            />
          ) : null}
        </div>
      ) : null}

      <div className="shell acct-layout">
        <div className="acct-panels">
          <Panel
            title="We think you like"
            action={chosen ? { href: '/account/preferences', label: 'Correct this →' } : undefined}
          >
            {chosen ? (
              <div className="acct-chips">
                {likes.map((label) => (
                  <span className="acct-chip" key={label}>
                    {label}
                  </span>
                ))}
              </div>
            ) : (
              <EmptyState
                lede="Nothing yet — we have not asked, and you have not said."
                hint={
                  <>
                    Pick a few things on the <Link href="/account/preferences">preferences page</Link> and
                    the site starts adjusting.
                  </>
                }
              />
            )}
          </Panel>

          <Panel title="Continue reading">
            <EmptyState
              lede="Nothing picked up yet."
              hint="Stories you read while signed in appear here."
            />
          </Panel>

          <Panel title="Saved">
            <EmptyState lede="Nothing kept yet." hint="The bookmark on any story keeps it here." />
          </Panel>

          <Panel title="Your itineraries">
            <EmptyState
              lede="No trips planned yet."
              hint="Build one from any place page and it will keep here."
            />
          </Panel>
        </div>

        <aside className="acct-aside">
          <Panel title="Membership">
            <EmptyState lede="Membership is not open yet." hint="We will tell you here first." />
          </Panel>

          <Panel title="This month's edition">
            <EmptyState
              lede="The edition is not live yet."
              hint="It will appear here the day it is."
            />
          </Panel>

          <Panel title="Account">
            <dl className="acct-dl">
              <dt>Email</dt>
              <dd>
                {reader.email}
                {reader.emailVerified ? null : (
                  <>
                    {' · '}
                    <Link href="/account/verify">confirm it</Link>
                  </>
                )}
              </dd>
            </dl>
            <form action={signOut} style={{ marginTop: 'var(--space-m)' }}>
              <button className="acct-btn acct-btn--ghost" type="submit">
                Sign out
              </button>
            </form>
          </Panel>
        </aside>
      </div>
    </>
  )
}
