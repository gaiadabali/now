import type { Metadata } from 'next'

import { getSiteConfig } from '@/lib/site'

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteConfig()
  return { title: 'Advertise', description: `Partner with ${site.name}` }
}

export default async function AdvertisePage() {
  const site = await getSiteConfig()
  const domain = site.hostname.replace(/^www\./, '')

  return (
    <div className="shell">
      <header className="band">
        <p className="kicker kicker--red">Advertise</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          Partner with us
        </h1>
        <p className="dek" style={{ marginTop: 'var(--space-m)', maxWidth: '46ch' }}>
          Reach readers who are deciding where to go this week.
        </p>
      </header>

      <section className="band" style={{ maxWidth: '62ch', display: 'grid', gap: 'var(--space-l)' }}>
        <div>
          <p className="kicker">How placements work</p>
          <p className="dek">
            A partnership attaches to a venue, not to an article. Sign one and every historical
            mention of that venue updates at once; let it lapse and they revert on the date it ends.
            Nothing is rewritten by hand.
          </p>
        </div>
        <div>
          <p className="kicker">What we will not do</p>
          <p className="dek">
            A paid placement never displaces a better answer, and a sponsored link is always marked
            as one. Relevance and billing are separate decisions.
          </p>
        </div>
        <div>
          <p className="kicker">Talk to us</p>
          <p className="dek">
            <a href={`mailto:partnerships@${domain}`}>partnerships@{domain}</a>
          </p>
        </div>
      </section>
    </div>
  )
}
