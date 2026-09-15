import type { Metadata } from 'next'
import Link from 'next/link'

import { areasWithCounts } from '@/lib/payload'
import { getSiteConfig } from '@/lib/site'

export const metadata: Metadata = {
  title: 'Areas',
  description: 'Neighbourhoods and districts we cover.',
}

export default async function AreasPage() {
  const site = await getSiteConfig()
  const areas = await areasWithCounts()

  return (
    <div className="shell">
      <header className="band">
        <p className="kicker kicker--red">Discover</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          Areas
        </h1>
        <p className="dek" style={{ marginTop: 'var(--space-m)', maxWidth: '46ch' }}>
          Every neighbourhood {site.name} writes about, with how much there is to read.
        </p>
      </header>

      {areas.length === 0 ? (
        <section className="band">
          <p className="dek">No areas are tagged yet.</p>
        </section>
      ) : (
        <section className="band">
          <div className="facets" style={{ flexWrap: 'wrap', gap: 'var(--space-xs)' }}>
            {areas.map((area) => (
              <Link
                className="facet"
                key={area.slug}
                href={`/search?facets=location:${encodeURIComponent(area.slug)}`}
              >
                {area.label} <span className="facet__count">{area.count}</span>
              </Link>
            ))}
          </div>
          <p className="dek" style={{ marginTop: 'var(--space-l)' }}>
            {areas.length} areas with published coverage.
          </p>
        </section>
      )}
    </div>
  )
}
