import type { Metadata } from 'next'
import Image from 'next/image'
import Link from 'next/link'

import { StoryCard } from '@/components/StoryCard'
import { SectionRule } from '@/components/primitives'
import { getCulture } from '@/lib/content'
import { getSiteConfig } from '@/lib/site'

/**
 * Culture.
 *
 * The one section that is NOT a `primaryType` filter. The §4 L1 vocabulary is
 * exactly do/drink/eat/editorial/event/shop/stay/wellness/unknown — there is
 * no `culture` label, and an earlier build that pretended otherwise returned
 * 500 on this very URL (`invalid input value for enum
 * enum_articles_primary_type: "culture"`).
 *
 * The subject lives in the taxonomy instead, spread over the `subtype` and
 * `format` facets: culture, heritage, people, art, music. So this page starts
 * from `engine.entity_terms` and fetches the matching articles by id.
 * Jakarta has 298 such articles today and Bali 353 — real coverage, which is
 * why this is worth a page rather than a redirect.
 *
 * This route is a static sibling of `[slug]`, so it wins the match and no
 * article can shadow it.
 */

export const metadata: Metadata = {
  title: 'Culture',
  description: 'Art, heritage, music and the people behind them.',
}

export default async function CulturePage() {
  const site = await getSiteConfig()
  const articles = await getCulture(24)
  const [lead, ...rest] = articles

  return (
    <div className="shell">
      <header className="band" style={{ paddingBottom: 'var(--space-l)' }}>
        <p className="kicker kicker--red">Section</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          Culture
        </h1>
        <p className="dek" style={{ marginTop: 'var(--space-s)', maxWidth: '46ch' }}>
          Art, heritage, music and the people behind them — what {site.name} is watching beyond the
          table and the check-in desk.
        </p>
      </header>

      {lead ? (
        <>
          <div className="lead">
            <div className="lead__body">
              <span className="kicker kicker--red">Leading</span>
              <h2
                className="lead__headline display display--light"
                style={{ fontSize: 'var(--t-headline)' }}
              >
                <Link href={`/${lead.slug}`}>{lead.title}</Link>
              </h2>
              <p className="dek">{lead.dek}</p>
            </div>
            {lead.image ? (
              <figure className="lead__figure">
                <Image
                  className="lead__img"
                  src={lead.image}
                  alt=""
                  width={1200}
                  height={900}
                  sizes="(max-width: 62rem) 100vw, 46vw"
                  priority
                  style={{ aspectRatio: '3 / 2' }}
                />
              </figure>
            ) : null}
          </div>

          <section className="band" style={{ paddingTop: 0 }}>
            <SectionRule label="More in culture" />
            <div className="grid grid--3 grid--ruled">
              {rest.map((a) => (
                <StoryCard
                  key={a.id}
                  article={a}
                  locale={site.locale}
                  timeZone={site.timezone}
                />
              ))}
            </div>
          </section>
        </>
      ) : (
        <section className="band">
          <p className="dek">
            Nothing is tagged to culture yet here. The classifier is still working through the
            archive.
          </p>
        </section>
      )}
    </div>
  )
}
