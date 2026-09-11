import Image from 'next/image'
import Link from 'next/link'

import { StoryCard } from '@/components/StoryCard'
import { PartnerBadge, SectionRule, Signup } from '@/components/primitives'
import { EVENTS, GUIDES, getLatest, getLead, getMostRead, sectionLabel, sectionOf } from '@/lib/content'
import { formatDate, formatDay, readingTime } from '@/lib/format'
import { getSiteConfig } from '@/lib/site'

export default async function HomePage() {
  const site = await getSiteConfig()
  const { locale, timezone: tz } = site
  const [lead, latest, mostRead] = await Promise.all([getLead(), getLatest(20), getMostRead(5)])
  const edit = latest.slice(1, 4)
  const rest = latest.slice(4, 12)

  return (
    <>
      {/* ---------------------------------------------------- feature lead */}
      <section className="shell">
        <div className="lead">
          <div className="lead__body">
            <div className="lead__kicker">
              <span className="kicker kicker--red">{sectionLabel(sectionOf(lead))}</span>
              <span className="kicker">/ The Feature</span>
            </div>
            <h1 className="lead__headline display display--light">
              <Link href={`/${lead.slug}`}>{lead.title}</Link>
            </h1>
            <p className="dek lead__dek">{lead.dek}</p>
            <div className="byline">
              <span>
                Words by <span className="byline__name">NOW! Editorial</span>
              </span>
              <span className="byline__sep">·</span>
              <time dateTime={lead.date}>{formatDate(lead.date, locale, tz)}</time>
              <span className="byline__sep">·</span>
              <span>{readingTime(lead.paras)} min read</span>
            </div>
          </div>
          <figure className="lead__figure">
            <Image
              className="lead__img"
              src={lead.image}
              alt=""
              width={1200}
              height={1500}
              sizes="(max-width: 62rem) 100vw, 46vw"
              priority
            />
          </figure>
        </div>
      </section>

      {/* ------------------------------------------------------- the edit */}
      <section className="shell band" style={{ paddingTop: 0 }}>
        <SectionRule label="The Edit" note="Chosen this week" moreHref="/latest" />
        <div className="grid grid--3 grid--ruled">
          {edit.map((a, i) => (
            <StoryCard
              key={a.id}
              article={a}
              variant="portrait"
              locale={locale}
              timeZone={tz}
              partner={i === 2}
            />
          ))}
        </div>
      </section>

      {/* ---------------------------------------------------------- guides */}
      <section className="shell band" style={{ paddingTop: 0 }}>
        <SectionRule label="The Guides" note="Kept current, not archived" moreHref="/guides" />
        <div className="grid grid--4">
          {GUIDES.map((g) => (
            <Link className="guide" key={g.href} href={g.href}>
              {g.image ? (
                <Image className="guide__img" src={g.image} alt="" width={600} height={600} sizes="25vw" />
              ) : null}
              <span className="guide__count display">{g.count}</span>
              <span className="guide__title">{g.title}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* ------------------------------------------- main well + side rail */}
      <section className="shell band" style={{ paddingTop: 0 }}>
        <div className="split">
          <div>
            <SectionRule label="Latest" moreHref="/latest" />
            <div className="rail__list">
              {rest.map((a, i) => (
                <div key={a.id} style={{ paddingBlock: 'var(--space-m)', borderBottom: 'var(--rule-hair)' }}>
                  <StoryCard
                    article={a}
                    variant="horizontal"
                    locale={locale}
                    timeZone={tz}
                    partner={i === 1}
                  />
                </div>
              ))}
            </div>
          </div>

          <aside className="rail">
            <div>
              <SectionRule label="Most Read" />
              <ol className="rail__list">
                {mostRead.map((a, i) => (
                  <li key={a.id}>
                    <StoryCard
                      article={a}
                      variant="index"
                      index={i + 1}
                      showDek={false}
                      locale={locale}
                      timeZone={tz}
                    />
                  </li>
                ))}
              </ol>
            </div>

            <div>
              <SectionRule label="What's On" moreHref="/events" />
              <ul>
                {EVENTS.map((e) => {
                  const d = formatDay(e.date, locale, tz)
                  return (
                    <li className="event" key={e.title}>
                      <span className="event__date">
                        <span className="event__day">{d.day}</span>
                        <span className="event__mon">{d.month}</span>
                      </span>
                      <span>
                        <span className="event__title">{e.title}</span>
                        <br />
                        <span className="event__where">{e.where}</span>
                      </span>
                    </li>
                  )
                })}
              </ul>
            </div>

            <Signup site={site} />

            <div>
              <SectionRule label="In Partnership" />
              <p className="meta" style={{ fontSize: 'var(--t-micro)' }}>
                Paid placements carry a <PartnerBadge /> mark wherever they appear — in rails, in
                indexes and on the page itself. Partner tier is never a sort option.
              </p>
            </div>
          </aside>
        </div>
      </section>
    </>
  )
}
