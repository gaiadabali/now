import type { Metadata } from 'next'
import Link from 'next/link'

import { SectionRule } from '@/components/primitives'
import { archiveStats } from '@/lib/payload'
import { getSiteConfig } from '@/lib/site'
import { formatCount } from '@/lib/format'

/**
 * Advertise.
 *
 * NO AUDIENCE FIGURES. The beacon is not live (§6), so we have no measured
 * readership — and a traffic number invented for a sales page is the single
 * worst thing on this site to get wrong, because someone would spend money on
 * it. What can be stated truthfully is the archive: how much there is, how
 * long it has run, how it is organised.
 *
 * No rate card either, for the same reason: rates are the client's to set.
 * The page describes what we offer and routes to the people who price it.
 */

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteConfig()
  return { title: 'Advertise', description: `Partner with ${site.name}.` }
}

const FORMATS = [
  {
    name: 'Sponsored feature',
    body: 'A full story about your venue, written to the same standard as our editorial and carrying a Partner label. It lives in the relevant section and stays in the archive.',
  },
  {
    name: 'Venue record',
    body: 'Your place as a structured record — hours, address, price band, booking link — kept current and surfaced wherever it is relevant, not just in one article.',
  },
  {
    name: 'Event listing',
    body: 'Dated, discoverable and tied to the neighbourhood it happens in, so it reaches people already reading about that area.',
  },
  {
    name: 'Newsletter placement',
    body: 'One email a week to people who asked for it. One placement per issue, so it is not competing with five others.',
  },
]

export default async function AdvertisePage() {
  const site = await getSiteConfig()
  const stats = await archiveStats()
  const n = formatCount
  const sales = site.contact?.sales ?? site.contact?.editorial

  return (
    <div className="shell">
      <header className="band">
        <p className="kicker kicker--red">Advertise</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          Work with us
        </h1>
        <p className="dek" style={{ marginTop: 'var(--space-m)', maxWidth: '48ch' }}>
          We reach people deciding where to eat, stay and spend their time — at the moment they are
          deciding.
        </p>
      </header>

      {stats.articles > 0 ? (
        <section className="band" style={{ paddingTop: 0 }}>
          <div className="place-facts">
            <div className="place-facts__row">
              <span className="place-facts__key">Archive</span>
              <span className="place-facts__val">{n(stats.articles)} stories</span>
            </div>
            {stats.sinceYear ? (
              <div className="place-facts__row">
                <span className="place-facts__key">Publishing since</span>
                <span className="place-facts__val">{stats.sinceYear}</span>
              </div>
            ) : null}
            {stats.areas > 0 ? (
              <div className="place-facts__row">
                <span className="place-facts__key">Places and topics tagged</span>
                <span className="place-facts__val">{n(stats.areas)}</span>
              </div>
            ) : null}
          </div>
          <p className="meta" style={{ marginTop: 'var(--space-s)', maxWidth: '52ch' }}>
            Readership figures are not published here. Our audience measurement is being rebuilt,
            and we would rather give you nothing than a number we cannot stand behind. Ask us and
            we will tell you exactly what we can and cannot evidence.
          </p>
        </section>
      ) : null}

      <section className="band" style={{ paddingTop: 0 }}>
        <SectionRule label="What we offer" />
        <div className="grid grid--3 grid--ruled">
          {FORMATS.map((f) => (
            <article key={f.name}>
              <h3 style={{ fontSize: 'var(--t-card)', marginBottom: 'var(--space-3xs)' }}>
                {f.name}
              </h3>
              <p className="dek">{f.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="band" style={{ paddingTop: 0 }}>
        <SectionRule label="How we label it" />
        <div className="prose" style={{ maxWidth: '62ch' }}>
          <p>
            Everything paid carries a <strong>Partner</strong> label on the page it appears. We do
            not run unmarked advertorial, and we will not agree to it.
          </p>
          <p>
            That is a commercial position as much as an ethical one: the reason a recommendation
            here is worth paying for is that readers can tell the difference. A paid placement
            never displaces a better answer to the question a reader asked.
          </p>
        </div>
      </section>

      <section className="band" style={{ paddingTop: 0 }}>
        <SectionRule label="Get a proposal" />
        <div className="prose" style={{ maxWidth: '62ch' }}>
          <p>
            Tell us the venue, the timing and roughly what you want to achieve, and we will come
            back with formats and rates.
          </p>
          {sales ? (
            <p>
              <a
                href={`mailto:${sales}?subject=${encodeURIComponent(`Advertising enquiry — ${site.name}`)}`}
                style={{ borderBottom: '1px solid var(--red)', fontWeight: 600 }}
              >
                {sales}
              </a>
            </p>
          ) : (
            <p>
              Reach us through{' '}
              <Link href="/contact" style={{ borderBottom: '1px solid var(--red)' }}>
                Contact
              </Link>
              .
            </p>
          )}
        </div>
      </section>
    </div>
  )
}
