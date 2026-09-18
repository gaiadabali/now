import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import { EntityBeacon } from '@/components/Beacon'
import { BandHead } from '@/components/primitives'
import { activePlaceBySlug } from '@/lib/payload'
import { getSiteConfig } from '@/lib/site'

/**
 * Place profile — the venue-shaped counterpart to an article.
 *
 * **This used to render a fixture.** It served `PLACE` — a hardcoded Ubud
 * restaurant — for every slug, in both cities, which is why a Jakarta URL
 * showed a Bali address. It was a comp that outlived the comp era.
 *
 * Now it reads the real row and 404s unless `status = 'active'`. Every venue
 * is still `pending_review` (F27), so this route 404s everywhere today. That
 * is correct: a profile is a set of factual claims about a business — where
 * it is, what it costs, when it opens — and none of them have been checked.
 * A 404 is the honest answer until one has been.
 *
 * No star ratings and no user reviews, whatever the status: NOW! speaks in
 * its own voice, and a partner must never be able to buy a score.
 */

type Params = { params: Promise<{ slug: string }> }

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params
  const place = await activePlaceBySlug(slug)
  if (!place) return {}
  return { title: place.name, description: [place.subtype, place.area].filter(Boolean).join(' · ') }
}

export default async function PlacePage({ params }: Params) {
  const { slug } = await params
  const site = await getSiteConfig()
  const place = await activePlaceBySlug(slug)
  if (!place) notFound()
  // Tells the layout's single beacon tag which place this page is (E8.5).
  const beacon = <EntityBeacon entity={String(place.id)} entityType="place" surface="place" />

  const facts: Array<[string, string]> = [
    ['Type', place.subtype ?? place.type ?? '—'],
    ['Area', place.area ?? '—'],
    ['Price', place.priceBand ?? '—'],
    ['Address', place.address ?? '—'],
  ].filter(([, v]) => v !== '—') as Array<[string, string]>

  return (
    <div className="shell">
      {beacon}
      <div className="place-head">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-m)' }}>
          <div style={{ display: 'flex', gap: 'var(--space-2xs)', alignItems: 'center' }}>
            <span className="kicker kicker--red">{place.subtype ?? place.type ?? 'Venue'}</span>
            {place.area ? <span className="kicker">/ {place.area}</span> : null}
          </div>
          <h1 className="place-head__title display display--light">{place.name}</h1>
        </div>

        <div className="place-facts">
          {facts.map(([key, value]) => (
            <div className="place-facts__row" key={key}>
              <span className="place-facts__key">{key}</span>
              <span className="place-facts__val">{value}</span>
            </div>
          ))}
        </div>
      </div>

      <section className="band">
        <BandHead title="Our Coverage" note={`Everything ${site.name} has written about ${place.name}`} />
        <p className="meta">
          Coverage links appear here once article&nbsp;→&nbsp;venue linking is applied to this
          record.
        </p>
      </section>
    </div>
  )
}
