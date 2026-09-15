import type { Metadata } from 'next'

import { getSiteConfig } from '@/lib/site'

export const metadata: Metadata = { title: 'Podcast' }

export default async function PodcastPage() {
  const site = await getSiteConfig()

  return (
    <div className="shell">
      <header className="band">
        <p className="kicker kicker--red">Podcast</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          Coming soon
        </h1>
        <p className="dek" style={{ marginTop: 'var(--space-m)', maxWidth: '46ch' }}>
          {site.name} is working on a show. Episodes will appear here, and in the usual places, when
          there are episodes to appear.
        </p>
      </header>
    </div>
  )
}
