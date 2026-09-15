import type { Metadata } from 'next'

import { getSiteConfig } from '@/lib/site'

/**
 * About.
 *
 * Copy comes from `site.config.json` per city (ARCHITECTURE.md §3.5: site
 * differences live in config rows, never in `src/`). There is no city name in
 * this file and there must not be — `npm run lint:site-literals` enforces it.
 */

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteConfig()
  return { title: 'About', description: `About ${site.name}` }
}

export default async function AboutPage() {
  const site = await getSiteConfig()

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
        <p className="dek" style={{ marginTop: 'var(--space-m)', maxWidth: '46ch' }}>
          {site.tagline}
        </p>
      </header>

      <section className="band" style={{ maxWidth: '62ch' }}>
        <p style={{ marginBottom: 'var(--space-m)' }}>
          We cover where to eat, drink, stay and spend time — reviewed by people who live here and
          kept current rather than left to age.
        </p>
        <p style={{ marginBottom: 'var(--space-m)' }}>
          Every venue we write about is a record in our own database, not a name in a sentence. That
          is what lets a guide stay accurate when a restaurant moves, changes hands or closes.
        </p>
        <p>
          Commercial partnerships are disclosed on the page they appear, and a paid placement never
          displaces a better answer to the question you asked.
        </p>
      </section>
    </div>
  )
}
