import Image from 'next/image'
import Link from 'next/link'

import { StoryCard } from '@/components/StoryCard'
import { Badge, PartnerBadge, SectionRule } from '@/components/primitives'
import { PLACE, getLatest } from '@/lib/content'
import { getSiteConfig } from '@/lib/site'

/**
 * Place profile. The venue-shaped counterpart to an article: facts on the
 * left as a rules table, editorial coverage below. No star ratings and no
 * user reviews — NOW! speaks in its own voice, and a partner must never be
 * able to buy a score.
 */
export default async function PlacePage() {
  const site = await getSiteConfig()
  const coverage = (await getLatest(4)).slice(1)
  const hero = (await getLatest(1))[0]
  const p = PLACE

  return (
    <div className="shell">
      <div className="place-head">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-m)' }}>
          <div style={{ display: 'flex', gap: 'var(--space-2xs)', alignItems: 'center' }}>
            <span className="kicker kicker--red">{p.type}</span>
            <span className="kicker">/ {p.area}</span>
            {p.partner ? <PartnerBadge /> : null}
          </div>
          <h1 className="place-head__title display display--light">{p.name}</h1>
          <p className="dek">{p.dek}</p>
          <div style={{ display: 'flex', gap: 'var(--space-2xs)', flexWrap: 'wrap' }}>
            {p.vibe.map((v) => (
              <Badge key={v}>{v}</Badge>
            ))}
          </div>
        </div>

        <div className="place-facts">
          <div className="place-facts__row">
            <span className="place-facts__key">Cuisine</span>
            <span className="place-facts__val">{p.cuisine}</span>
          </div>
          <div className="place-facts__row">
            <span className="place-facts__key">Price</span>
            <span className="place-facts__val price">
              {'$'.repeat(p.price)}
              <span className="price__off">{'$'.repeat(4 - p.price)}</span>
            </span>
          </div>
          <div className="place-facts__row">
            <span className="place-facts__key">Area</span>
            <span className="place-facts__val">
              <Link href="/areas/ubud" style={{ borderBottom: '1px solid var(--red)' }}>
                {p.area}
              </Link>
              , {p.district}
            </span>
          </div>
          <div className="place-facts__row">
            <span className="place-facts__key">Hours</span>
            <span className="place-facts__val">{p.hours}</span>
          </div>
          <div className="place-facts__row">
            <span className="place-facts__key">Address</span>
            <span className="place-facts__val">{p.address}</span>
          </div>
          <div className="place-facts__row">
            <span className="place-facts__key">Telephone</span>
            <span className="place-facts__val">{p.phone}</span>
          </div>
        </div>
      </div>

      <figure>
        <Image
          className="article-hero__img"
          src={hero.image}
          alt=""
          width={1600}
          height={900}
          sizes="100vw"
          priority
        />
        <figcaption className="figure__caption">
          {p.name}, {p.area}. <span className="figure__credit">Photo courtesy of the venue.</span>
        </figcaption>
      </figure>

      <section className="band">
        <SectionRule label="Our Coverage" note={`Everything we have written about ${p.name}`} />
        <div className="grid grid--3 grid--ruled">
          {coverage.map((a) => (
            <StoryCard key={a.id} article={a} locale={site.locale} timeZone={site.timezone} />
          ))}
        </div>
      </section>

      <section className="band" style={{ paddingTop: 0 }}>
        <SectionRule label="Nearby" note="Within 15 minutes" moreHref="/areas/ubud" />
        <p className="meta">
          Distance-ranked results appear here once geocoding completes — 141 venues are still waiting
          on a Maps key (PROGRESS.md, blocker&nbsp;0).
        </p>
      </section>
    </div>
  )
}
