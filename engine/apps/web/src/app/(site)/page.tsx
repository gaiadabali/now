import Image from 'next/image'
import Link from 'next/link'

import { StoryCard } from '@/components/StoryCard'
import { Band, BandHead, AreaIndex, Signup } from '@/components/primitives'
import { getFrontPage } from '@/lib/frontPage'
import { sectionLabel, sectionOf } from '@/lib/content'
import { readerContextFromRequest } from '@/lib/recommend'
import { formatDate } from '@/lib/format'

/**
 * The home page — Edition 2's front page, assembled by `lib/frontPage.ts`
 * and rendered here without a query of its own (DESIGN-SYSTEM "the desk
 * writes them, the home page reads them").
 *
 * Rebuilt for the owner's first complaint: "the first screen is masthead
 * plus a single 21:9 cover — no secondary top stories, no timestamped
 * latest." The `lead` band is now a package rather than a single image: a
 * large lead, 3–4 secondary top stories beside it, and a timestamped strip
 * below both — sized (masthead ≈230px + package ≈650px on a 1440×900
 * laptop, measured against the built production bundle) so the next band's
 * own heading is the thing peeking into view, not a hard cut mid-band.
 *
 * Every band after the lead is real content or it does not render — S2's
 * honesty policy, unchanged. What changed is that `getFrontPage` now also
 * guarantees no story repeats across bands (the Hotels band no longer
 * re-leads with the story the front page just told) and that the desk's
 * `home_rails` pins and ordering are honoured when set.
 */
export default async function HomePage() {
  // `readerContextFromRequest()` (lib/recommend.ts) is the ONE place that
  // knows both the beacon's anonymous id AND a signed-in reader's identity.
  // The previous version called `currentReader()` directly and handed
  // `getFrontPage` only `{ identityId }` — an anonymous first visit (no
  // `identityId`, the common case) reached `getForYou` with an EMPTY
  // `ReaderContext`, so "For you" could never fire before sign-up, however
  // much beacon history that visitor had. `getForYou` (lib/recommend.ts)
  // already reads `anonId` when there is no `identityId`; it was this call
  // site dropping it before it ever arrived.
  const reader = await readerContextFromRequest()
  const { site, bands } = await getFrontPage(reader)
  const { locale, timezone: tz } = site

  if (bands.length === 0) {
    return (
      <Band>
        <div className="shell">
          <p className="kicker kicker--red">Nothing published yet</p>
          <h1 className="bandhead__title" style={{ marginTop: 'var(--space-s)' }}>
            {site.name} is being prepared.
          </h1>
          <p className="dek" style={{ marginTop: 'var(--space-m)' }}>
            There are no published stories in this edition yet. Please check back shortly.
          </p>
        </div>
      </Band>
    )
  }

  return (
    <>
      {bands.map((band) => {
        switch (band.kind) {
          case 'lead': {
            const { hero, secondaries, ticker } = band
            return (
              <Band key="lead" hair className="band--lead">
                <div className="shell">
                  <div className="frontlead">
                    <Link className="frontlead__hero" href={`/${hero.slug}`}>
                      <span className="frontlead__media">
                        <Image
                          className="frontlead__hero-img"
                          src={hero.image}
                          alt=""
                          fill
                          sizes="(max-width: 62rem) 100vw, 60vw"
                          priority
                        />
                        <span className="frontlead__scrim" aria-hidden="true" />
                      </span>
                      <span className="frontlead__body">
                        <span className="cover__kicker">
                          {sectionLabel(sectionOf(hero))} / The Feature
                        </span>
                        <span
                          className="cover__headline"
                          data-nowb-entity={String(hero.id)}
                          data-nowb-entity-type="article"
                          data-nowb-rail="lead"
                          data-nowb-position="1"
                        >
                          {hero.title}
                        </span>
                        <span className="cover__meta">{formatDate(hero.date, locale, tz)}</span>
                      </span>
                    </Link>

                    {secondaries.length > 0 ? (
                      <div className="frontlead__secondaries" data-reveal>
                        <p className="kicker" style={{ marginBottom: 'var(--space-2xs)' }}>
                          Also this week
                        </p>
                        {secondaries.map((a, i) => (
                          <StoryCard
                            key={a.id}
                            article={a}
                            variant="horizontal"
                            locale={locale}
                            timeZone={tz}
                            rail="lead"
                            position={i + 2}
                          />
                        ))}
                        {/* The owner's note: this column needs a way on to
                            the next stories, not a dead end after three. */}
                        <Link className="frontlead__more" href="/latest">
                          More this week <span aria-hidden="true">→</span>
                        </Link>
                      </div>
                    ) : null}
                  </div>

                  {ticker.length > 0 ? (
                    <div className="fronticker" data-reveal>
                      <span className="fronticker__label">
                        <span className="fronticker__dot" aria-hidden="true" />
                        Just in
                      </span>
                      {ticker.map((a, i) => (
                        <span className="fronticker__item" key={a.id}>
                          <Link
                            href={`/${a.slug}`}
                            data-nowb-entity={String(a.id)}
                            data-nowb-entity-type="article"
                            data-nowb-rail="ticker"
                            data-nowb-position={i + 1}
                          >
                            {a.title}
                          </Link>
                          <time className="fronticker__time" dateTime={a.date}>
                            {formatDate(a.date, locale, tz)}
                          </time>
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              </Band>
            )
          }

          case 'edit':
            return (
              <Band key={band.key} reveal>
                <div className="shell">
                  <BandHead kicker={band.kicker} title={band.title} moreHref="/latest" moreLabel="Latest" />
                  <div className="grid--edit">
                    {band.items.map((a, i) => (
                      <StoryCard
                        key={a.id}
                        article={a}
                        variant="portrait"
                        locale={locale}
                        timeZone={tz}
                        rail="the-edit"
                        position={i + 1}
                      />
                    ))}
                  </div>
                </div>
              </Band>
            )

          case 'for-you':
            return (
              <Band key={band.key} tone="ivory" reveal>
                <div className="shell">
                  <BandHead kicker={band.rail.kicker} title={band.rail.title} />
                  <div className="grid--edit">
                    {band.rail.items.map((a) => (
                      <StoryCard key={a.id} article={a} variant="portrait" locale={locale} timeZone={tz} rail={a.rail} position={a.position} />
                    ))}
                  </div>
                </div>
              </Band>
            )

          case 'department': {
            const [side1, ...sideRest] = band.side
            const sideList = side1 ? (
              <div className="grid--dept__side">
                <StoryCard article={side1} variant="horizontal" showDek={false} locale={locale} timeZone={tz} rail={band.key} position={2} />
                {sideRest.map((a, i) => (
                  <StoryCard key={a.id} article={a} variant="horizontal" showDek={false} locale={locale} timeZone={tz} rail={band.key} position={i + 3} />
                ))}
              </div>
            ) : null

            // Three treatments (lib/bandVariant.ts) so an editor stacking
            // several `department:*` bands never repeats "1 large + 3 side
            // on ivory" back to back — DESIGN-SYSTEM's "adjacent bands must
            // not share a grid" and "--ivory once per page" both apply the
            // moment there is more than one. `priority` is never set here:
            // that belongs to the lead package's own hero, the one image
            // this page ever marks as the LCP candidate, and a department
            // band is never the first thing painted.
            if (band.variant === 'mirror') {
              // The same `.grid--dept` grid, mirrored: the side list on the
              // left, the lead on the right, on `--paper` rather than
              // `--ivory` (already spent by the first department band).
              return (
                <Band key={band.key} reveal>
                  <div className="shell">
                    <BandHead kicker={band.kicker} title={band.title} moreHref={band.moreHref} moreLabel={`Every ${band.title.toLowerCase()}`} />
                    <div className="grid--dept grid--dept--mirror">
                      {sideList}
                      <StoryCard article={band.lead} locale={locale} timeZone={tz} rail={band.key} position={1} />
                    </div>
                  </div>
                </Band>
              )
            }

            if (band.variant === 'quad') {
              // The Edit's own 4-up portrait grid, reused rather than a new
              // one invented for this: the lead and the side items fold
              // into one row of equals instead of a lead-plus-list.
              const quad = [band.lead, ...band.side].slice(0, 4)
              return (
                <Band key={band.key} reveal>
                  <div className="shell">
                    <BandHead kicker={band.kicker} title={band.title} moreHref={band.moreHref} moreLabel={`Every ${band.title.toLowerCase()}`} />
                    <div className="grid--edit">
                      {quad.map((a, i) => (
                        <StoryCard key={a.id} article={a} variant="portrait" locale={locale} timeZone={tz} rail={band.key} position={i + 1} />
                      ))}
                    </div>
                  </div>
                </Band>
              )
            }

            return (
              <Band key={band.key} tone="ivory" reveal>
                <div className="shell">
                  <BandHead kicker={band.kicker} title={band.title} moreHref={band.moreHref} moreLabel={`Every ${band.title.toLowerCase()}`} />
                  <div className="grid--dept">
                    <StoryCard article={band.lead} locale={locale} timeZone={tz} rail={band.key} position={1} />
                    {sideList}
                  </div>
                </div>
              </Band>
            )
          }

          case 'guides':
            return (
              <Band key={band.key} tone="ink" reveal>
                <div className="shell">
                  <BandHead kicker={band.kicker} title={band.title} moreHref="/guides" moreLabel="Every guide" />
                  {band.items.map((a, i) => (
                    <StoryCard key={a.id} article={a} variant="rank" index={i + 1} locale={locale} timeZone={tz} rail={band.key} position={i + 1} />
                  ))}
                </div>
              </Band>
            )

          case 'latest':
            return (
              <Band key={band.key} reveal>
                <div className="shell">
                  <BandHead kicker={band.kicker} title={band.title} moreHref="/latest" moreLabel="Load more stories" />
                  <div className="grid--index">
                    {band.items.map((a, i) => (
                      <StoryCard key={a.id} article={a} variant="row" locale={locale} timeZone={tz} rail={band.key} position={i + 1} />
                    ))}
                  </div>
                </div>
              </Band>
            )

          case 'explore':
            return (
              <Band key={band.key} hair reveal>
                <div className="shell">
                  <BandHead kicker={band.kicker} title={band.title} moreHref="/areas" moreLabel="Every area" />
                  <AreaIndex areas={band.areas} />
                  <p className="meta meta--micro" style={{ marginTop: 'var(--space-m)' }}>
                    Counts are stories published about each area.
                  </p>
                </div>
              </Band>
            )

          default:
            return null
        }
      })}

      <Band hair>
        <div className="shell">
          <Signup site={site} />
        </div>
      </Band>
    </>
  )
}
