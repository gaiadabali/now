import type { Metadata } from 'next'
import Link from 'next/link'

import { BandHead } from '@/components/primitives'
import { subscribe } from '@/lib/newsletter'
import { archiveStats } from '@/lib/payload'
import { getSiteConfig } from '@/lib/site'
import { formatCount } from '@/lib/format'

/**
 * Subscribe.
 *
 * The form now WORKS. Until this page it posted to `/api/subscribe`, a route
 * that has never existed, so every address typed into it was discarded
 * silently — a decorative call to action on every page of the site.
 *
 * It is a plain server-action form: no client JavaScript, so it submits on a
 * page that has not hydrated, and the outcome is a redirect with a status in
 * the URL rather than client state. That also makes every outcome a real,
 * linkable page rather than something only reachable by submitting.
 */

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteConfig()
  return {
    title: 'Subscribe',
    description: `The weekly edit from ${site.name} — one email, once a week.`,
  }
}

const STATUS: Record<string, { tone: 'ok' | 'bad'; head: string; body: string }> = {
  ok: {
    tone: 'ok',
    head: 'You are on the list.',
    body: 'We have your address. Nothing else is needed from you — the next edition will arrive on schedule.',
  },
  invalid: {
    tone: 'bad',
    head: 'That address did not look right.',
    body: 'Check it for a typo and try once more.',
  },
  error: {
    tone: 'bad',
    head: 'Something went wrong at our end.',
    body: 'Your address was not saved. Please try again in a moment.',
  },
}

export default async function SubscribePage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}) {
  const site = await getSiteConfig()
  const stats = await archiveStats()
  const query = (await searchParams) ?? {}
  const status = typeof query.status === 'string' ? STATUS[query.status] : undefined

  return (
    <div className="shell">
      <header className="band">
        <p className="kicker kicker--red">The Weekly</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          Everything worth your attention, once a week.
        </h1>
        <p className="dek" style={{ marginTop: 'var(--space-m)', maxWidth: '48ch' }}>
          What opened, what closed, what is worth the trip — edited down to one email you can read
          in the time it takes to finish a coffee.
        </p>
      </header>

      <section className="band" style={{ paddingTop: 0 }}>
        {status ? (
          <div
            className="pullquote"
            style={{
              marginBottom: 'var(--space-l)',
              borderLeftColor: status.tone === 'ok' ? 'var(--red)' : undefined,
            }}
            role="status"
          >
            <p className="pullquote__text" style={{ fontSize: 'var(--t-title)' }}>
              {status.head}
            </p>
            <p className="meta" style={{ marginTop: 'var(--space-2xs)' }}>
              {status.body}
            </p>
          </div>
        ) : null}

        <form className="signup__form" action={subscribe} style={{ maxWidth: '34rem' }}>
          <label className="visually-hidden" htmlFor="subscribe-email">
            Email address
          </label>
          <input
            className="signup__input"
            id="subscribe-email"
            name="email"
            type="email"
            autoComplete="email"
            placeholder="your@email.com"
            required
          />
          <input type="hidden" name="source" value="subscribe-page" />
          <button className="signup__btn" type="submit">
            Join
          </button>
        </form>
        <p className="meta" style={{ marginTop: 'var(--space-xs)', maxWidth: '46ch' }}>
          One email a week, never more. We do not sell or share your address, and every edition has
          an unsubscribe link that works on the first click.
        </p>
      </section>

      <section className="band" style={{ paddingTop: 0 }}>
        <BandHead title="What you get" />
        <div className="grid grid--3 grid--ruled">
          <article>
            <h3 style={{ fontSize: 'var(--t-title)', marginBottom: 'var(--space-3xs)' }}>
              The short list
            </h3>
            <p className="dek">
              Five or six things, chosen because they are worth your time — not because they were
              published this week.
            </p>
          </article>
          <article>
            <h3 style={{ fontSize: 'var(--t-title)', marginBottom: 'var(--space-3xs)' }}>
              Openings and closings
            </h3>
            <p className="dek">
              What is new, and what has quietly gone — the second being the harder thing to find
              out anywhere else.
            </p>
          </article>
          <article>
            <h3 style={{ fontSize: 'var(--t-title)', marginBottom: 'var(--space-3xs)' }}>
              From the archive
            </h3>
            <p className="dek">
              {stats.articles > 0
                ? `One thing worth rereading from the ${formatCount(stats.articles)} stories behind us.`
                : 'One thing worth rereading from the archive.'}
            </p>
          </article>
        </div>
      </section>

      <section className="band" style={{ paddingTop: 0 }}>
        <BandHead title="While you wait" />
        <p className="dek" style={{ maxWidth: '52ch' }}>
          Start with{' '}
          <Link href="/guides" style={{ borderBottom: '1px solid var(--red)' }}>
            the guides
          </Link>
          , or browse{' '}
          <Link href="/areas" style={{ borderBottom: '1px solid var(--red)' }}>
            by area
          </Link>
          .
        </p>
      </section>
    </div>
  )
}
