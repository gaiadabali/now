import type { Metadata } from 'next'
import Link from 'next/link'

import { BandHead } from '@/components/primitives'
import type { AreaTerm } from '@/lib/payload'
import { locationTree } from '@/lib/payload'
import { getSiteConfig } from '@/lib/site'
import { formatCount } from '@/lib/format'

/**
 * Areas.
 *
 * One flat count-sorted list put BALI, UBUD and SEMINYAK next to EUROPE,
 * JAPAN and NORTH JAKARTA in a wall of ninety-odd chips. Accurate, and
 * useless for finding a neighbourhood — a reader on the Bali site is looking
 * for Canggu, not Cambodia.
 *
 * The taxonomy is already a tree (`indonesia` / `international` roots, cities
 * beneath, sub-regions beneath those), so this groups rather than sorts: this
 * city first and broken into its regions, then the rest of Indonesia, then
 * international coverage last.
 *
 * No city name appears in this file. The local group is keyed off
 * `site.slug` — §3.5, enforced by `npm run lint:site-literals`.
 */

export const metadata: Metadata = {
  title: 'Areas',
  description: 'Every neighbourhood and destination we cover, by region.',
}

function Chips({ items }: { items: AreaTerm[] }) {
  return (
    <div className="facets" style={{ flexWrap: 'wrap', gap: 'var(--space-xs)' }}>
      {items.map((t) => (
        <Link
          className="facet"
          key={t.slug}
          href={`/search?facets=location:${encodeURIComponent(t.slug)}`}
        >
          {t.label} <span className="facet__count">{formatCount(t.count)}</span>
        </Link>
      ))}
    </div>
  )
}

export default async function AreasPage() {
  const site = await getSiteConfig()
  const tree = await locationTree(site.slug)
  const hasAnything =
    tree.local.regions.length > 0 || tree.indonesia.length > 0 || tree.international.length > 0

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
          Where {site.name} has been — neighbourhood by neighbourhood at home, and everywhere else
          we have travelled for a story.
        </p>
      </header>

      {!hasAnything ? (
        <section className="band">
          <p className="dek">No areas are tagged yet.</p>
        </section>
      ) : null}

      {tree.local.regions.length > 0 ? (
        <section className="band" style={{ paddingTop: 0 }}>
          <BandHead
            title={tree.local.label}
            note={`${formatCount(tree.local.total)} stories close to home`}
          />
          {tree.local.own && tree.local.own.count > 0 ? (
            <div style={{ marginBottom: 'var(--space-l)' }}>
              <Chips items={[{ ...tree.local.own, label: `All of ${tree.local.own.label}` }]} />
            </div>
          ) : null}

          {tree.local.regions.map((region) => (
            <div key={region.slug} style={{ marginBottom: 'var(--space-l)' }}>
              <p className="kicker" style={{ marginBottom: 'var(--space-2xs)' }}>
                {region.label}{' '}
                <span className="facet__count">{formatCount(region.count)}</span>
              </p>
              {region.areas.length > 0 ? (
                <Chips items={region.areas} />
              ) : (
                <p className="meta">Tagged at region level only.</p>
              )}
            </div>
          ))}
        </section>
      ) : null}

      {tree.indonesia.length > 0 ? (
        <section className="band" style={{ paddingTop: 0 }}>
          <BandHead title="Elsewhere in Indonesia" />
          <Chips items={tree.indonesia} />
        </section>
      ) : null}

      {tree.international.length > 0 ? (
        <section className="band" style={{ paddingTop: 0 }}>
          <BandHead title="International" note="Where we have travelled" />
          <Chips items={tree.international} />
        </section>
      ) : null}
    </div>
  )
}
