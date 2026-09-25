import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect, notFound } from 'next/navigation'

import { AccountShell, EmptyState, Panel, StatusBanner, type StatusMessage } from '@/components/account'
import { StoryCard } from '@/components/StoryCard'
import { currentReader, accountsEnabled } from '@/lib/reader'
import { signOut } from '@/lib/readerActions'
import { toggleSaved } from '@/lib/savedActions'
import { getSavedArticles } from '@/lib/savedItems'
import { describePrefs, hasChosen, loadPrefs, loadVocabulary } from '@/lib/preferences'
import { getForYou, readerContextFromRequest } from '@/lib/recommend'
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

  // Resolved once, ahead of the batch below: `getForYou` needs it as an
  // argument rather than a promise, and it is cheap (a cookie read plus the
  // already-`cache()`-wrapped `currentReader()` — see lib/reader.ts).
  const readerContext = await readerContextFromRequest()
  const [vocabulary, prefs, site, forYou, savedArticles] = await Promise.all([
    loadVocabulary(),
    loadPrefs(reader.id),
    getSiteConfig(),
    getForYou(readerContext),
    getSavedArticles(reader.id),
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
        <div className="acct-main">
          {/* The dashboard's lead (§4 update — "the dashboard shows no
              stories at all" was the specific complaint this panel answers).
              `getForYou` already excludes competitor rivals, diversifies by
              series and carries its own honest label — "Because you like
              Ubud and Wellness" or "Because of what you read" — which is
              rendered here as the panel's own subtitle rather than invented
              copy of this page's own. */}
          <Panel title="Picked for you">
            {forYou ? (
              <>
                <p className="acct-foryou__reason">{forYou.title}</p>
                <div className="acct-card-grid">
                  {forYou.items.map((a) => (
                    <StoryCard
                      key={a.id}
                      article={a}
                      variant="horizontal"
                      showDek={false}
                      locale={site.locale}
                      timeZone={site.timezone}
                      rail={a.rail}
                      position={a.position}
                    />
                  ))}
                </div>
              </>
            ) : (
              <EmptyState
                lede="Nothing picked for you yet."
                hint={
                  <>
                    Tell us what you are into on the <Link href="/account/preferences">preferences page</Link>{' '}
                    and this fills in — or keep reading, and it will fill in on its own.
                  </>
                }
              />
            )}
          </Panel>

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

            {/* Real now: `getSavedArticles` reads `engine.saved_items`
                (lib/savedItems.ts), which the article page's Save toggle
                writes to. Given the full row §4's removed itineraries panel
                left behind (see below) — it is the one main panel likely to
                hold more than one or two items, and a compact grid reads
                better across the whole column than squeezed into half of
                it. */}
            <Panel title="Saved" className="acct-panel--wide">
              {savedArticles.length > 0 ? (
                <div className="acct-card-grid">
                  {savedArticles.map((a) => (
                    <div className="acct-saved-item" key={a.id}>
                      <StoryCard
                        article={a}
                        variant="horizontal"
                        showDek={false}
                        locale={site.locale}
                        timeZone={site.timezone}
                      />
                      <form action={toggleSaved}>
                        <input type="hidden" name="entityId" value={a.id} />
                        <input type="hidden" name="intent" value="unsave" />
                        <input type="hidden" name="returnTo" value="/account" />
                        <button className="acct-remove-btn" type="submit">
                          Remove from saved
                        </button>
                      </form>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState lede="Nothing kept yet." hint="The bookmark on any story keeps it here." />
              )}
            </Panel>

            {/* "Your itineraries" is gone, not emptied. §4's own rule —
                "an empty panel still renders, with an invitation" — assumes
                the invitation is honest, and this one was not: "Build one
                from any place page and it will keep here" promised a
                mechanism (an itinerary builder, reachable from a place page)
                that does not exist. `/places` itself is "coming soon" today,
                so the panel was inviting a reader to a page that cannot do
                what the copy says. E5.4 is the itinerary builder; this
                panel returns the day that ships, with the same honesty
                every other panel here already gets. Until then the extra
                width above went to Saved, which now has real content to use
                it for. */}
          </div>
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
