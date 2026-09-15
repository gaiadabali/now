import type { Metadata } from 'next'

import { getSiteConfig } from '@/lib/site'

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteConfig()
  return { title: 'Contact', description: `Get in touch with ${site.name}` }
}

export default async function ContactPage() {
  const site = await getSiteConfig()
  // Addresses come from the site row, not from this file — one city's inbox
  // must never appear on the other's page (§3.5).
  const domain = site.hostname.replace(/^www\./, '')

  return (
    <div className="shell">
      <header className="band">
        <p className="kicker kicker--red">Contact</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          Get in touch
        </h1>
      </header>

      <section className="band" style={{ maxWidth: '54ch', display: 'grid', gap: 'var(--space-l)' }}>
        <div>
          <p className="kicker">Editorial</p>
          <p className="dek">
            Story tips, corrections and review requests —{' '}
            <a href={`mailto:editorial@${domain}`}>editorial@{domain}</a>
          </p>
        </div>
        <div>
          <p className="kicker">Partnerships</p>
          <p className="dek">
            Campaigns, listings and placements —{' '}
            <a href={`mailto:partnerships@${domain}`}>partnerships@{domain}</a>
          </p>
        </div>
        <div>
          <p className="kicker">Corrections</p>
          <p className="dek">
            If we have something wrong, tell us and we will fix the record rather than the sentence.
          </p>
        </div>
      </section>
    </div>
  )
}
