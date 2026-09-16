import type { Metadata } from 'next'
import Image from 'next/image'
import Link from 'next/link'
import { notFound } from 'next/navigation'

import { EntityBeacon } from '@/components/Beacon'
import { StoryCard } from '@/components/StoryCard'
import { SectionRule, Signup } from '@/components/primitives'
import {
  getBySlug,
  getSectionPage,
  getSectionFacets,
  getRelated,
  isSectionSlug,
  sectionLabel,
  sectionOf,
} from '@/lib/content'
import { formatCount, formatDate, readingTime } from '@/lib/format'
import { stripTags } from '@/lib/html'
import { getSiteConfig } from '@/lib/site'

/**
 * One dynamic segment serves both article and section, because legacy
 * permalinks are flat (`/%postname%/`, confirmed in LIVE_RECON) and must keep
 * working at the domain root. Sections resolve first; anything else is looked
 * up as an article. This is the routing decision that protects the SEO
 * estate — do not split it into sibling dynamic routes.
 */

type Params = {
  params: Promise<{ slug: string }>
  // The facet chips are links, so the active filter lives in the URL. That
  // keeps a filtered section shareable and back-button-able, and keeps this
  // page a server component — no client state for something the URL already
  // expresses.
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}

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

export default async function SlugPage({ params, searchParams }: Params) {
  const { slug } = await params
  const query = (await searchParams) ?? {}
  const format = typeof query.format === 'string' ? query.format : undefined
  const page = Number.parseInt(typeof query.page === 'string' ? query.page : '1', 10)
  if (isSectionSlug(slug)) {
    return <SectionIndex slug={slug} format={format} page={Number.isFinite(page) ? page : 1} />
  }
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
  // Tells the layout's single beacon tag which article this page is (E8.5).
  const beacon = <EntityBeacon entity={String(article.id)} entityType="article" surface="article" />
  const section = sectionOf(article)

  // Pull quote is lifted from the body rather than authored separately, the
  // way a sub-editor would. In production this comes from a `pullquote`
  // block in the Lexical body (see `bodyBlocks.ts` in the CMS package).
  const quoteIndex = Math.min(3, article.paras.length - 1)
  // Plain text: a pull quote is typeset, not marked up, and slicing it to 180
  // characters would otherwise cut through the middle of a tag.
  const quote = stripTags(article.paras[quoteIndex] ?? '')

  return (
    <article>
      {beacon}
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
            <span>{readingTime(article.paras.map(stripTags))} min read</span>
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
            {/*
              dangerouslySetInnerHTML is correct here and the name is louder
              than the risk: `article.paras` is sanitised in the mapper (see
              lib/payload.ts), so a page cannot receive unvetted markup. The
              alternative — what this used to do — escaped the archive's own
              formatting and printed `<strong>` tags at readers.
            */}
            {article.paras.slice(0, quoteIndex + 1).map((p, i) => (
              <p key={i} dangerouslySetInnerHTML={{ __html: p }} />
            ))}

            <figure className="pullquote">
              <p className="pullquote__text">
                {quote.length > 180 ? `${quote.slice(0, 180).trimEnd()}…` : quote}
              </p>
              <figcaption className="pullquote__attr">From the report</figcaption>
            </figure>

            {article.paras.slice(quoteIndex + 1).map((p, i, arr) => (
              <p key={i}>
                <span dangerouslySetInnerHTML={{ __html: p }} />
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

const PER_PAGE = 24

async function SectionIndex({
  slug,
  format,
  page = 1,
}: {
  slug: string
  format?: string
  page?: number
}) {
  const site = await getSiteConfig()
  const { locale, timezone: tz } = site
  const result = await getSectionPage(slug, { page, limit: PER_PAGE, format })
  const articles = result.items
  // A page number past the end is a bad URL, not an empty section. Without
  // this, ?page=9999 renders a section that looks like it has no articles.
  if (articles.length === 0 && page > 1) notFound()
  // The lead treatment only makes sense on the first page; on page 3 the
  // newest article of that slice is not "leading" anything.
  const isFirstPage = result.page <= 1
  const [lead, ...rest] = isFirstPage ? articles : []

  // Real counts, faceted on `format`, computed from the database.
  //
  // These were hardcoded comp values — `Ubud 34`, `Seminyak 28`, `$$ 41` —
  // wired to nothing. They neither counted nor filtered, and on Jakarta they
  // showed BALI place names, because the comp borrowed a places filter for an
  // articles page. Area and price are attributes of `places`; a section index
  // lists `articles`, whose reader-facing facet is format.
  const facets = await getSectionFacets(slug)

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
        {facets.map((f) => {
          const active = (f.value ?? undefined) === format
          return (
            <Link
              className="facet"
              key={f.label}
              href={f.value ? `/${slug}?format=${encodeURIComponent(f.value)}` : `/${slug}`}
              aria-pressed={active}
              data-active={active || undefined}
            >
              {f.label} <span className="facet__count">{f.count}</span>
            </Link>
          )
        })}
        <span className="facets__result">
          {formatCount(result.total)} {result.total === 1 ? 'story' : 'stories'}
          {result.totalPages > 1 ? ` · page ${result.page} of ${result.totalPages}` : ''}
        </span>
      </div>

      {isFirstPage && lead ? (
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
          {(isFirstPage ? rest : articles).map((a, i) => (
            <StoryCard
              key={a.id}
              article={a}
              locale={locale}
              timeZone={tz}
              partner={isFirstPage && i === 0}
            />
          ))}
        </div>
        {articles.length === 0 ? (
          <p className="meta">Nothing in this section yet.</p>
        ) : null}
        <Pager slug={slug} format={format} page={result.page} totalPages={result.totalPages} />
      </section>
    </div>
  )
}


/**
 * Section pagination.
 *
 * Links, not buttons: the page is a server component and the URL already
 * expresses the state, so a paged section stays shareable, crawlable and
 * back-button-able. Same reasoning as the facet chips above.
 *
 * Only a window of numbers is rendered. Dining has 39 pages and Unclassified
 * has 50 — a full run of page links would be longer than the content.
 */
function Pager({
  slug,
  format,
  page,
  totalPages,
}: {
  slug: string
  format?: string
  page: number
  totalPages: number
}) {
  if (totalPages <= 1) return null

  const href = (n: number) => {
    const qs = new URLSearchParams()
    if (format) qs.set('format', format)
    if (n > 1) qs.set('page', String(n))
    const q = qs.toString()
    return `/${slug}${q ? `?${q}` : ''}`
  }

  const window_ = 2
  const numbers: number[] = []
  for (let n = Math.max(1, page - window_); n <= Math.min(totalPages, page + window_); n++) {
    numbers.push(n)
  }

  return (
    <nav className="facets" style={{ marginTop: 'var(--space-l)' }} aria-label="Pagination">
      {page > 1 ? (
        <Link className="facet" href={href(page - 1)} rel="prev">
          ← Newer
        </Link>
      ) : null}

      {numbers[0] > 1 ? (
        <>
          <Link className="facet" href={href(1)}>
            1
          </Link>
          {numbers[0] > 2 ? <span className="meta">…</span> : null}
        </>
      ) : null}

      {numbers.map((n) => (
        <Link
          className="facet"
          key={n}
          href={href(n)}
          aria-current={n === page ? 'page' : undefined}
          data-active={n === page || undefined}
        >
          {n}
        </Link>
      ))}

      {numbers[numbers.length - 1] < totalPages ? (
        <>
          {numbers[numbers.length - 1] < totalPages - 1 ? <span className="meta">…</span> : null}
          <Link className="facet" href={href(totalPages)}>
            {totalPages}
          </Link>
        </>
      ) : null}

      {page < totalPages ? (
        <Link className="facet" href={href(page + 1)} rel="next">
          Older →
        </Link>
      ) : null}
    </nav>
  )
}
