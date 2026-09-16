import type { Metadata } from 'next'
import Link from 'next/link'

import { activePlaces, placeReviewCounts } from '@/lib/payload'
import { getSiteConfig } from '@/lib/site'
import { formatCount } from '@/lib/format'

/**
 * Places — the venue directory.
 *
 * **This page deliberately shows nothing today, and that is the feature.**
 * Every one of the 6,589 Jakarta and 5,918 Bali venue records is still
 * `status = 'pending_review'` (F27, recorded launch-blocking). Those rows
 * came out of the archive with addresses, price bands and opening claims that
 * no editor has checked. Listing them would publish twelve thousand
 * unverified factual assertions under NOW!'s name, and a venue record is
 * exactly the kind of thing a reader acts on — they drive there.
 *
 * So the index reads `status = 'active'` and fills in on its own as review
 * progresses. No code change is needed when it does; the page simply stops
 * being empty. The pending count is shown because an unexplained empty page
 * reads as broken, and this one is not.
 */

export const metadata: Metadata = {
  title: 'Places',
  description: 'Every venue we have verified.',
}

export default async function PlacesPage() {
  const site = await getSiteConfig()
  const [places, counts] = await Promise.all([activePlaces(120), placeReviewCounts()])

  return (
    <div className="shell">
      <header className="band">
        <p className="kicker kicker--red">Directory</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          Places
        </h1>
        <p className="dek" style={{ marginTop: 'var(--space-m)', maxWidth: '46ch' }}>
          Every venue {site.name} has verified — each one a record we keep current, not a name in a
          sentence.
        </p>
      </header>

      {places.length === 0 ? (
        <section className="band">
          <p className="dek" style={{ maxWidth: '52ch' }}>
            The directory is not open yet. We are working through{' '}
            {formatCount(counts.pending)} venue records from the archive and will
            list each one only once an editor has checked it.
          </p>
          <p className="dek" style={{ marginTop: 'var(--space-m)' }}>
            In the meantime, our coverage is in the{' '}
            <Link href="/dining" style={{ borderBottom: '1px solid var(--red)' }}>
              sections
            </Link>
            .
          </p>
        </section>
      ) : (
        <section className="band">
          <div className="grid grid--3 grid--ruled">
            {places.map((p) => (
              <article key={p.slug}>
                <p className="kicker kicker--red">{p.subtype ?? p.type ?? 'Venue'}</p>
                <h2 style={{ fontSize: 'var(--t-card)', marginTop: 'var(--space-3xs)' }}>
                  <Link href={`/places/${p.slug}`}>{p.name}</Link>
                </h2>
                <p className="meta">
                  {[p.area, p.priceBand].filter(Boolean).join(' · ') || p.address}
                </p>
              </article>
            ))}
          </div>
          <p className="dek" style={{ marginTop: 'var(--space-l)' }}>
            {formatCount(places.length)} verified of{' '}
            {formatCount(counts.total)}.
          </p>
        </section>
      )}
    </div>
  )
}
