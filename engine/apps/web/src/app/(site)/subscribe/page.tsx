import type { Metadata } from 'next'

import { Signup } from '@/components/primitives'
import { getSiteConfig } from '@/lib/site'

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteConfig()
  return { title: 'Subscribe', description: `The ${site.name} newsletter` }
}

export default async function SubscribePage() {
  const site = await getSiteConfig()

  return (
    <div className="shell">
      <header className="band">
        <p className="kicker kicker--red">Subscribe</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          The weekly edit
        </h1>
        <p className="dek" style={{ marginTop: 'var(--space-m)', maxWidth: '46ch' }}>
          What opened, what is worth your time, and what we would book this week. One email, no
          filler.
        </p>
      </header>

      {/* The same component the footer uses, so there is one signup form in the
          codebase rather than two that drift apart. */}
      <section className="band">
        <Signup site={site} />
      </section>
    </div>
  )
}
