import type { Metadata } from 'next'
import { draftMode } from 'next/headers'
import Image from 'next/image'
import Link from 'next/link'
import { notFound } from 'next/navigation'

import { ReadNextBand, PlanAroundBand } from '@/components/ArticleRails'
import { EntityBeacon } from '@/components/Beacon'
import { SaveButton } from '@/components/SaveButton'
import { StoryCard } from '@/components/StoryCard'
import { Signup } from '@/components/primitives'
import {
  getBySlug,
  getSectionPage,
  getSectionFacets,
  isSectionSlug,
  sectionLabel,
  sectionOf,
} from '@/lib/content'
import { formatCount, formatDate, readingTime } from '@/lib/format'
import { firstWholeSentence, stripTags } from '@/lib/html'
import { accountsEnabled, currentReader } from '@/lib/reader'
import { getArticleRails } from '@/lib/recommend'
import { isSaved } from '@/lib/savedItems'
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
  // Draft mode here too, or previewing an unpublished story shows the tab
  // title of whatever was published at that address before — or nothing.
  // `robots` is the part that matters: an unpublished draft must not be
  // indexable even in the window where a crawler somehow holds the cookie.
  const draft = (await draftMode()).isEnabled
  const article = await getBySlug(slug, { draft })
  if (!article) return {}
  return {
    title: article.title,
    description: article.dek,
    openGraph: { title: article.title, description: article.dek, images: [article.image], type: 'article' },
    ...(draft ? { robots: { index: false, follow: false } } : {}),
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
  // Preview (S4). The cookie is set only by `/preview`, which checks for an
  // editorial role first, so this is a staff browser asking for the newest
  // version rather than the published one. Everyone else takes the `false`
  // branch and cannot reach a draft from any URL.
  const draft = (await draftMode()).isEnabled
  const article = await getBySlug(slug, { draft })
  if (!article) notFound()
  return <ArticlePage slug={slug} draft={draft} />
}

/* ========================================================================== */
/*  ARTICLE                                                                   */
/* ========================================================================== */

async function ArticlePage({ slug, draft = false }: { slug: string; draft?: boolean }) {
  const site = await getSiteConfig()
  const { locale, timezone: tz } = site
  const article = (await getBySlug(slug, { draft }))!
  const rails = await getArticleRails(article)
  // Tells the layout's single beacon tag which article this page is (E8.5).
  const beacon = <EntityBeacon entity={String(article.id)} entityType="article" surface="article" />
  const section = sectionOf(article)

  // The Save toggle (DESIGN-SYSTEM §3's "must not appear" list: "a Save
  // affordance with no persistence behind it" — this is the write path that
  // rule was waiting on). `currentReader()` is `cache()`-wrapped
  // (lib/reader.ts), so this costs nothing extra when the layout above has
  // already read it for the masthead.
  const reader = await currentReader()
  const saved = reader ? await isSaved(reader.id, article.id) : false

  // Pull quote is lifted from the body rather than authored separately, the
  // way a sub-editor would. In production this comes from a `pullquote`
  // block in the Lexical body (see `bodyBlocks.ts` in the CMS package).
  //
  // Starts at the same paragraph as before (the 4th, or the last one there
  // is) and tries `firstWholeSentence` on it; if that paragraph's own first
  // sentence does not fit whole, tries the NEXT paragraph, and so on to the
  // end of the article. A magazine does not truncate a pull quote — the
  // previous version fell back to a word-boundary cut and still ended
  // "...management through…", grammatically clean and still not what the
  // source said. If nothing in the article produces a whole sentence
  // within the limit, `quote` stays `null` and no pull quote renders at
  // all; `quoteAt` is where the body splits around it, and stays at the
  // ORIGINAL paragraph when nothing was found, so the layout is unaffected
  // by a search that came up empty.
  const PULL_QUOTE_MIN_WORDS = 10
  const startAt = Math.min(3, article.paras.length - 1)
  let quote: string | null = null
  let quoteAt = startAt
  for (let i = startAt; i < article.paras.length; i++) {
    const candidate = firstWholeSentence(stripTags(article.paras[i] ?? ''), 180)
    // A pull quote is a line worth setting large. A whole sentence can still
    // be opening hours ("Open daily from 11am to 10pm.", which the first
    // Edition 2 build put under a restaurant review) — under ten words it is
    // information, not a quote, and the search moves on.
    if (candidate && candidate.split(/\s+/).length >= PULL_QUOTE_MIN_WORDS) {
      quote = candidate
      quoteAt = i
      break
    }
  }
  const shareUrl = `https://www.${site.hostname}/${article.slug}`

  return (
    <article>
      {/* Reading progress (DESIGN-SYSTEM motion). `animation-timeline:
          scroll(root)` only — see magazine.css for what an unsupported
          browser gets instead, which is an inert bar, not a broken one. */}
      <div className="readbar" aria-hidden="true">
        <span className="readbar__fill" />
      </div>
      {beacon}
      {/* Says, on the page, that this page is not the published one.
          Draft mode is a cookie that outlives the story being previewed, so
          without this an editor goes on seeing unpublished versions of
          everything they open with no indication of it — and eventually
          reports a bug against a page only they can see. The way out is a
          plain link, not a hidden keystroke. */}
      {draft ? (
        <div className="preview-bar">
          <span className="shell preview-bar__inner">
            <strong>Preview</strong> — showing the latest saved version, which may be unpublished.
            Nobody else can see this.
            <a className="preview-bar__exit" href={`/preview/exit?to=/${slug}`}>
              Leave preview
            </a>
          </span>
        </div>
      ) : null}
      <div className="shell">
        <header className="article-head">
          <p className="lead__kicker">
            <Link className="kicker kicker--red" href={`/${section}`}>
              {sectionLabel(section)}
            </Link>
          </p>
          <h1 className="article-head__title display display--light">{article.title}</h1>
          <p className="dek">{article.dek}</p>
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

              Split around `quoteAt` only when a pull quote was actually
              found (`quote !== null`, see above) — nothing in the archive
              guarantees one exists that fits whole, and a magazine renders
              NO pull quote rather than a truncated one when it does not. The
              paragraphs before the split have no endmark to carry, so they
              render plain; the endmark always belongs to the true last
              paragraph, which is why every paragraph after the split (or
              every paragraph, when there is no split at all) is wrapped so
              it can carry one as a sibling rather than fight
              `dangerouslySetInnerHTML` for a `<p>`'s only child slot.
            */}
            {article.paras.slice(0, quote ? quoteAt + 1 : 0).map((p, i) => (
              <p key={i} dangerouslySetInnerHTML={{ __html: p }} />
            ))}

            {quote ? (
              <figure className="pullquote">
                <p className="pullquote__text">{quote}</p>
                <figcaption className="pullquote__attr">From the report</figcaption>
              </figure>
            ) : null}

            {article.paras.slice(quote ? quoteAt + 1 : 0).map((p, i, arr) => (
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
            {/* Sticky: the previous aside "held only a newsletter box" and
                ended where the prose happened to run out. Share now leads
                it, and the whole rail tracks the reader down the column —
                `top` backs off when the header condenses (magazine.css),
                so it never overlaps the smaller header either. */}
            <div className="aside-sticky">
              <div className="share" id="share">
                <p className="bandhead__kicker">Share this story</p>
                <div className="share__list">
                  {/* The Save toggle leads the list — the reader's own copy
                      of the story, above sending it to someone else.
                      Renders nothing when accounts are unreachable
                      (F141: the site must never show a control that leads
                      to a 404), and a plain sign-in link (with a way back
                      to right here) rather than a form when signed out. */}
                  <SaveButton
                    articleId={article.id}
                    articlePath={`/${article.slug}`}
                    saved={saved}
                    accountsEnabled={accountsEnabled()}
                    signedIn={Boolean(reader)}
                  />
                  {/* Real, zero-JS shares — no Web Share API plumbing to
                      hydrate for two links. WhatsApp first: the highest-
                      traffic share channel for a reader in either city. */}
                  <a
                    className="share__link"
                    href={`https://wa.me/?text=${encodeURIComponent(`${article.title} ${shareUrl}`)}`}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    WhatsApp <span aria-hidden="true">↗</span>
                  </a>
                  <a
                    className="share__link"
                    href={`mailto:?subject=${encodeURIComponent(article.title)}&body=${encodeURIComponent(shareUrl)}`}
                  >
                    Email <span aria-hidden="true">↗</span>
                  </a>
                </div>
              </div>
              <Signup site={site} />
            </div>
          </aside>
        </div>
      </div>

      {/* Every rail comes from lib/recommend.ts, already chosen, ordered and
          labelled. Do not add a rail here that recommends by this story's own
          section: on a hotel story that is a rail of hotels, which is the one
          thing this page must never show (recommend.ts, "The one rule").
          Read Next is the only rail every article gets, venue or not, and
          stays its own full band. On a venue story the engine also returns
          up to three `plan-<section>` rails ("Plan around it") — grouped
          into ONE band with a column each (see ArticleRails.tsx), so a
          hotel story does not end with four stacked 3-up bands. Today's
          stub returns Read Next only, so `PlanAroundBand` renders nothing —
          it is already correct for the day the engine starts sending them. */}
      <ReadNextBand rail={rails.find((r) => r.key === 'read-next')} locale={locale} timeZone={tz} />
      <PlanAroundBand rails={rails.filter((r) => r.key.startsWith('plan-'))} locale={locale} timeZone={tz} />
    </article>
  )
}

/* ========================================================================== */
/*  SECTION INDEX                                                             */
/* ========================================================================== */

const PER_PAGE = 24

/**
 * The index treatment (DESIGN-SYSTEM §3: "an index, not a feed"), not cards.
 *
 * The previous version led with one enlarged card and filled the rest of the
 * page with `grid--3 grid--ruled` — a card grid, the exact thing §2 singles
 * out for not being able to hold an archive at any density. A section can
 * run to 39 pages (dining); the index rows below are what makes that
 * scrollable rather than a slideshow.
 */
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
          Everything we are watching in {sectionLabel(slug).toLowerCase()} — reviewed and kept current.
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

      <section className="band" style={{ paddingTop: 0 }} data-reveal>
        <div className="grid--index">
          {articles.map((a, i) => (
            <StoryCard key={a.id} article={a} variant="row" locale={locale} timeZone={tz} rail={slug} position={i + 1} />
          ))}
        </div>
        {articles.length === 0 ? <p className="meta">Nothing in this section yet.</p> : null}
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
