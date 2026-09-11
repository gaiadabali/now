import type { Metadata } from 'next'
import Image from 'next/image'
import Link from 'next/link'
import { notFound } from 'next/navigation'

import { StoryCard } from '@/components/StoryCard'
import { SectionRule, Signup } from '@/components/primitives'
import {
  getBySection,
  getBySlug,
  getRelated,
  isSectionSlug,
  sectionLabel,
  sectionOf,
} from '@/lib/content'
import { formatDate, readingTime } from '@/lib/format'
import { getSiteConfig } from '@/lib/site'

/**
 * One dynamic segment serves both article and section, because legacy
 * permalinks are flat (`/%postname%/`, confirmed in LIVE_RECON) and must keep
 * working at the domain root. Sections resolve first; anything else is looked
 * up as an article. This is the routing decision that protects the SEO
 * estate — do not split it into sibling dynamic routes.
 */

type Params = { params: Promise<{ slug: string }> }

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params
  if (isSectionSlug(slug)) return { title: sectionLabel(slug) }
  const article = await getBySlug(slug)
  if (!article) return {}
  return {
    title: article.title,
    description: article.dek,
    openGraph: { title: article.title, description: article.dek, images: [article.image], type: 'article' },
  }
}

export default async function SlugPage({ params }: Params) {
  const { slug } = await params
  if (isSectionSlug(slug)) return <SectionIndex slug={slug} />
  const article = await getBySlug(slug)
  if (!article) notFound()
  return <ArticlePage slug={slug} />
}

/* ========================================================================== */
/*  ARTICLE                                                                   */
/* ========================================================================== */

async function ArticlePage({ slug }: { slug: string }) {
  const site = await getSiteConfig()
  const { locale, timezone: tz } = site
  const article = (await getBySlug(slug))!
  const related = await getRelated(article)
  const section = sectionOf(article)

  // Pull quote is lifted from the body rather than authored separately, the
  // way a sub-editor would. In production this comes from a `pullquote`
  // block in the Lexical body (see `bodyBlocks.ts` in the CMS package).
  const quoteIndex = Math.min(3, article.paras.length - 1)
  const quote = article.paras[quoteIndex]

  return (
    <article>
      <div className="shell">
        <header className="article-head">
          <p className="lead__kicker">
            <Link className="kicker kicker--red" href={`/${section}`}>
              {sectionLabel(section)}
            </Link>
          </p>
          <h1 className="article-head__title display display--light">{article.title}</h1>
          <p className="dek" style={{ maxWidth: '38ch' }}>
            {article.dek}
          </p>
          <div className="byline">
            <span>
              Words by <span className="byline__name">NOW! Editorial</span>
            </span>
            <span className="byline__sep">·</span>
            <time dateTime={article.date}>{formatDate(article.date, locale, tz)}</time>
            <span className="byline__sep">·</span>
            <span>{readingTime(article.paras)} min read</span>
          </div>
        </header>
      </div>

      <figure className="shell">
        <Image
          className="article-hero__img"
          src={article.image}
          alt=""
          width={1600}
          height={900}
          sizes="100vw"
          priority
        />
        <figcaption className="figure__caption">
          {article.title}. <span className="figure__credit">Photo courtesy of the venue.</span>
        </figcaption>
      </figure>

      <div className="shell band">
        <div className="split">
          <div className="prose">
            {article.paras.slice(0, quoteIndex + 1).map((p, i) => (
              <p key={i}>{p}</p>
            ))}

            <figure className="pullquote">
              <p className="pullquote__text">
                {quote.length > 180 ? `${quote.slice(0, 180).trimEnd()}…` : quote}
              </p>
              <figcaption className="pullquote__attr">From the report</figcaption>
            </figure>

            {article.paras.slice(quoteIndex + 1).map((p, i, arr) => (
              <p key={i}>
                {p}
                {i === arr.length - 1 ? <span className="endmark" aria-label="End of article" /> : null}
              </p>
            ))}

            {article.tags.length ? (
              <p className="meta" style={{ marginTop: 'var(--space-xl)' }}>
                Filed under{' '}
                {article.tags.map((t, i) => (
                  <span key={t}>
                    {i > 0 ? ', ' : ''}
                    <Link href={`/search?tag=${encodeURIComponent(t)}`} style={{ color: 'var(--red)' }}>
                      {t}
                    </Link>
                  </span>
                ))}
              </p>
            ) : null}
          </div>

          <aside className="rail">
            <Signup site={site} />
          </aside>
        </div>
      </div>

      {related.length ? (
        <section className="shell band" style={{ paddingTop: 0 }}>
          <SectionRule label="Read Next" note="Chosen by the engine" moreHref={`/${section}`} />
          <div className="grid grid--3 grid--ruled">
            {related.map((a) => (
              <StoryCard key={a.id} article={a} locale={locale} timeZone={tz} />
            ))}
          </div>
        </section>
      ) : null}
    </article>
  )
}

/* ========================================================================== */
/*  SECTION INDEX                                                             */
/* ========================================================================== */

async function SectionIndex({ slug }: { slug: string }) {
  const site = await getSiteConfig()
  const { locale, timezone: tz } = site
  const articles = await getBySection(slug, 12)
  const [lead, ...rest] = articles

  // Facet counts are illustrative in the comp. Live, they come from the
  // engine's single aggregate pass, computed with every filter EXCEPT the
  // facet being counted (ARCHITECTURE.md §9).
  const facets = [
    { label: 'All', count: articles.length, active: true },
    { label: 'Ubud', count: 34 },
    { label: 'Seminyak', count: 28 },
    { label: 'Canggu', count: 22 },
    { label: '$$', count: 41 },
    { label: '$$$', count: 19 },
    { label: 'Open now', count: 12 },
  ]

  return (
    <div className="shell">
      <header className="band" style={{ paddingBottom: 'var(--space-l)' }}>
        <p className="kicker kicker--red">Section</p>
        <h1 className="display display--light" style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}>
          {sectionLabel(slug)}
        </h1>
        <p className="dek" style={{ marginTop: 'var(--space-s)' }}>
          Everything we are watching in {sectionLabel(slug).toLowerCase()} — reviewed, ranked and kept
          current.
        </p>
      </header>

      <div className="facets">
        {facets.map((f) => (
          <button className="facet" key={f.label} type="button" aria-pressed={Boolean(f.active)}>
            {f.label} <span className="facet__count">{f.count}</span>
          </button>
        ))}
        <span className="facets__result">{articles.length} stories</span>
      </div>

      {lead ? (
        <div className="lead">
          <div className="lead__body">
            <span className="kicker kicker--red">Leading</span>
            <h2 className="lead__headline display display--light" style={{ fontSize: 'var(--t-headline)' }}>
              <Link href={`/${lead.slug}`}>{lead.title}</Link>
            </h2>
            <p className="dek">{lead.dek}</p>
          </div>
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
        </div>
      ) : null}

      <section className="band" style={{ paddingTop: 0 }}>
        <SectionRule label="More in this section" />
        <div className="grid grid--3 grid--ruled">
          {rest.map((a, i) => (
            <StoryCard key={a.id} article={a} locale={locale} timeZone={tz} partner={i === 0} />
          ))}
        </div>
        {!rest.length ? (
          <p className="meta">Nothing else here yet — the classifier is still filling this section.</p>
        ) : null}
      </section>
    </div>
  )
}
