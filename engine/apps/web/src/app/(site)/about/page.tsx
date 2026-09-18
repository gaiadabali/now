import type { Metadata } from 'next'
import Link from 'next/link'

import { BandHead } from '@/components/primitives'
import { archiveStats } from '@/lib/payload'
import { getSiteConfig } from '@/lib/site'
import { formatCount } from '@/lib/format'

/**
 * About.
 *
 * Every number on this page is READ FROM THE ARCHIVE at request time rather
 * than typed in. A figure someone wrote once is wrong within a month and
 * nobody notices; a figure derived from the data cannot drift.
 *
 * Deliberately no audience or traffic claims. The beacon is not live (§6 —
 * it is also why `views` is hardcoded to 0), so we have no measured
 * readership, and inventing one on the page that explains who we are would
 * be a poor place to start.
 *
 * No city name in this file — `npm run lint:site-literals` enforces it.
 */

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteConfig()
  return { title: 'About', description: `What ${site.name} covers, and how.` }
}

export default async function AboutPage() {
  const site = await getSiteConfig()
  const stats = await archiveStats()
  const n = formatCount

  return (
    <div className="shell">
      <header className="band">
        <p className="kicker kicker--red">About</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          {site.name}
        </h1>
        <p className="dek" style={{ marginTop: 'var(--space-m)', maxWidth: '48ch' }}>
          {site.tagline}
        </p>
      </header>

      {stats.articles > 0 ? (
        <section className="band" style={{ paddingTop: 0 }}>
          <div className="place-facts">
            <div className="place-facts__row">
              <span className="place-facts__key">Stories published</span>
              <span className="place-facts__val">{n(stats.articles)}</span>
            </div>
            {stats.sinceYear ? (
              <div className="place-facts__row">
                <span className="place-facts__key">Publishing since</span>
                <span className="place-facts__val">{stats.sinceYear}</span>
              </div>
            ) : null}
            {stats.authors > 0 ? (
              <div className="place-facts__row">
                <span className="place-facts__key">Contributors</span>
                <span className="place-facts__val">{n(stats.authors)}</span>
              </div>
            ) : null}
            {stats.areas > 0 ? (
              <div className="place-facts__row">
                <span className="place-facts__key">Places and topics tagged</span>
                <span className="place-facts__val">{n(stats.areas)}</span>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      <section className="band" style={{ paddingTop: 0 }}>
        <BandHead title="What we do" />
        <div className="prose" style={{ maxWidth: '62ch' }}>
          <p>
            We cover where to eat, drink, stay and spend time — written by people who live here,
            and kept current rather than left to age. If a restaurant moves, changes hands or
            closes, that is a correction to make, not a post to leave standing.
          </p>
          <p>
            Every venue we write about is a record in our own database, not a name in a sentence.
            That is what lets a guide stay accurate: when something changes, it changes in one
            place and every story that mentions it follows.
          </p>
          <p>
            We do not run star ratings and we do not publish user reviews. We say what we think in
            our own voice and put our name on it.
          </p>
        </div>
      </section>

      <section className="band" style={{ paddingTop: 0 }}>
        <BandHead title="How we handle commercial work" />
        <div className="prose" style={{ maxWidth: '62ch' }}>
          <p>
            Some of what we publish is paid for. When it is, it carries a{' '}
            <strong>Partner</strong> label on the page it appears, every time — not in a policy
            nobody reads.
          </p>
          <p>
            A paid placement never displaces a better answer to the question you asked, and no
            partner can buy a score, because there are no scores to buy. If you want to work with
            us, the details are on{' '}
            <Link href="/advertise" style={{ borderBottom: '1px solid var(--red)' }}>
              Advertise
            </Link>
            .
          </p>
        </div>
      </section>

      <section className="band" style={{ paddingTop: 0 }}>
        <BandHead title="Corrections" />
        <div className="prose" style={{ maxWidth: '62ch' }}>
          <p>
            If something here is wrong — a price, an address, an opening time, a name — tell us and
            we will fix it. That is the whole point of keeping venues as records.{' '}
            <Link href="/contact" style={{ borderBottom: '1px solid var(--red)' }}>
              Get in touch
            </Link>
            .
          </p>
        </div>
      </section>
    </div>
  )
}
