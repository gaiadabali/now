import Image from 'next/image'
import Link from 'next/link'

import { StoryCard } from '@/components/StoryCard'
import { Band, BandHead, AreaIndex, Signup } from '@/components/primitives'
import { getLatest, getLead, getSectionPage, sectionLabel, sectionOf } from '@/lib/content'
import { areasWithCounts } from '@/lib/payload'
import { formatCount, formatDate } from '@/lib/format'
import { getSiteConfig } from '@/lib/site'

/**
 * The home page, rebuilt on the band system (DESIGN-SYSTEM §2/§3).
 *
 * Every band below is real content, fetched here, or it is not rendered —
 * S2 already settled that an empty rail is hidden rather than shown empty
 * (Most Read has no traffic yet, every event is 2016–2020), and nothing in
 * this rebuild reopens that. What changed is the SHAPE of the page, not its
 * honesty policy: the previous layout was a lead plus a two-column
 * well-and-rail that put Most Read, "What's On" and the newsletter in one
 * sidebar. §3's home spec does not carry a sidebar at all — cover, The Edit,
 * one department, one franchise band, Latest, Explore, a subscribe foot —
 * so Most Read and events have no slot to reappear in here even once they
 * have data. That is a page-shape decision, not a re-litigation of S2; if a
 * future band wants them, it is a new band, not a rail bolted onto this one.
 *
 * The franchise band (§2's "oversized numeral + text + one portrait, on
 * `--ink`") needed a real, ranked, image-bearing rail and the archive has
 * exactly one that fits all three: the guides, newest first — the same
 * ordering every other band on this page uses, so numbering them 1–5 claims
 * nothing beyond "these are recent," not "these are best." A quality
 * ranking is not a thing this archive can back today (§10's presentation
 * bias warning is exactly the reason recency was never relabelled as rank).
 */
export default async function HomePage() {
  const site = await getSiteConfig()
  const { locale, timezone: tz } = site

  const [lead, latest, hotels, guides, areas] = await Promise.all([
    getLead(),
    getLatest(21),
    getSectionPage('stay', { limit: 4 }),
    getSectionPage('guides', { limit: 5 }),
    areasWithCounts(),
  ])

  // A real database can be empty — a freshly provisioned city has no
  // articles until the load runs. A masthead over a crash is worse than a
  // masthead over an honest empty state.
  if (!lead) {
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

  // getLatest(21) includes the lead itself (newest-first, and the lead IS
  // the newest article) — excluded here so The Edit and Latest never repeat
  // the story the cover already told.
  const rest = latest.filter((a) => a.id !== lead.id)
  const edit = rest.slice(0, 4)
  const index = rest.slice(4, 16)

  const [hotel, ...hotelSide] = hotels.items

  return (
    <>
      {/* --------------------------------------------------------- cover -- */}
      <div className="cover">
        <Image
          className="cover__img"
          src={lead.image}
          alt=""
          fill
          sizes="100vw"
          priority
        />
        <div className="cover__body">
          <div className="shell">
            <p className="cover__kicker">{sectionLabel(sectionOf(lead))} / The Feature</p>
            <h1 className="cover__headline">
              <Link
                href={`/${lead.slug}`}
                data-nowb-entity={String(lead.id)}
                data-nowb-entity-type="article"
                data-nowb-rail="cover"
                data-nowb-position="1"
              >
                {lead.title}
              </Link>
            </h1>
            <p className="cover__meta">{formatDate(lead.date, locale, tz)}</p>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------- the edit -- */}
      <Band>
        <div className="shell">
          <BandHead kicker="Chosen this week" title="The Edit" moreHref="/latest" moreLabel="Latest" />
          <div className="grid--edit">
            {edit.map((a, i) => (
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

      {/* -------------------------------------------------- department: Hotels */}
      {hotel ? (
        <Band tone="ivory">
          <div className="shell">
            <BandHead
              kicker={`${formatCount(hotels.total)} STORIES`}
              title="Hotels"
              moreHref="/stay"
              moreLabel="Every stay"
            />
            <div className="grid--dept">
              <StoryCard article={hotel} locale={locale} timeZone={tz} priority rail="hotels" position={1} />
              <div className="grid--dept__side">
                {hotelSide.map((a, i) => (
                  <StoryCard
                    key={a.id}
                    article={a}
                    variant="horizontal"
                    showDek={false}
                    locale={locale}
                    timeZone={tz}
                    rail="hotels"
                    position={i + 2}
                  />
                ))}
              </div>
            </div>
          </div>
        </Band>
      ) : null}

      {/* ---------------------------------------------- franchise: The Guides */}
      {guides.items.length > 0 ? (
        <Band tone="ink">
          <div className="shell">
            <BandHead
              kicker={`${formatCount(guides.total)} GUIDES`}
              title="The Guides"
              moreHref="/guides"
              moreLabel="Every guide"
            />
            {guides.items.map((a, i) => (
              <StoryCard
                key={a.id}
                article={a}
                variant="rank"
                index={i + 1}
                locale={locale}
                timeZone={tz}
                rail="guides"
                position={i + 1}
              />
            ))}
          </div>
        </Band>
      ) : null}

      {/* ------------------------------------------------------------ latest */}
      {index.length > 0 ? (
        <Band>
          <div className="shell">
            <BandHead kicker="Newest first" title="Latest" moreHref="/latest" moreLabel="Load more stories" />
            <div className="grid--index">
              {index.map((a, i) => (
                <StoryCard
                  key={a.id}
                  article={a}
                  variant="row"
                  locale={locale}
                  timeZone={tz}
                  rail="latest"
                  position={i + 1}
                />
              ))}
            </div>
          </div>
        </Band>
      ) : null}

      {/* ----------------------------------------------------------- explore
          `--paper`, not `--ivory`: §1 spends ivory on "one department given
          weight" — Hotels already is it — and files an index (which Explore
          is) under `--paper` explicitly ("news and indexes"). Two ivory
          bands on one page would spend the same restraint twice. */}
      {areas.length > 0 ? (
        <Band hair>
          <div className="shell">
            <BandHead kicker={`${formatCount(areas.length)} NEIGHBOURHOODS`} title="Explore" moreHref="/areas" moreLabel="Every area" />
            <AreaIndex areas={areas.slice(0, 12)} />
            <p className="meta meta--micro" style={{ marginTop: 'var(--space-m)' }}>
              Counts are stories published about each area.
            </p>
          </div>
        </Band>
      ) : null}

      {/* -------------------------------------------------------- subscribe */}
      <Band hair>
        <div className="shell">
          <Signup site={site} />
        </div>
      </Band>
    </>
  )
}
