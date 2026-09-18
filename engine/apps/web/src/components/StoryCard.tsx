import Image from 'next/image'
import Link from 'next/link'

import { PartnerBadge } from '@/components/primitives'
import type { Article } from '@/lib/content'
import { sectionOf, sectionLabel } from '@/lib/content'
import { formatDate, readingTime } from '@/lib/format'

type Variant = 'standard' | 'portrait' | 'horizontal' | 'index' | 'row' | 'rank'

/**
 * The single story card for the whole site. One component, six variants —
 * a second card component is how design systems start to rot, so new needs
 * become a variant here or they do not exist.
 *
 * S6 added two variants the broadsheet system never needed, because its one
 * grid never needed them: `row`, for Latest's dense no-thumbnail index
 * (DESIGN-SYSTEM §2 — "holds roughly three times the stories per screen that
 * a card grid does"), and `rank`, for the franchise band's oversized numeral
 * against `--ink`. Both are still this component rather than new ones,
 * because both are still "an article, rendered smaller" — the thing this
 * card exists to guarantee never drifts into two implementations.
 */
export function StoryCard({
  article,
  variant = 'standard',
  index,
  showDek = true,
  partner = false,
  locale,
  timeZone,
  priority = false,
  rail,
  position,
}: {
  article: Article
  variant?: Variant
  /** The numeral for `index` and `rank`. 1-based; rendered zero-padded. */
  index?: number
  showDek?: boolean
  partner?: boolean
  locale: string
  timeZone: string
  priority?: boolean
  /**
   * Which rail rendered this card, and where in it (1-based). Both or
   * neither: a position without a rail cannot be corrected for position bias
   * and a rail without a position is the bias itself, unmeasured.
   *
   * Untagged, a click on this card reaches the beacon as a bare URL — the
   * entity is only inferable by re-resolving the href server-side, and the
   * fact that a rail showed it is lost outright. Tagged, the click carries
   * the article id, the rail and the slot, and `BeaconRoute` can register the
   * impression that ARCHITECTURE §10's ranker needs to know what was shown
   * and not clicked.
   */
  rail?: string
  position?: number
}) {
  const section = sectionOf(article)
  const href = `/${article.slug}`
  const withImage = variant !== 'index' && variant !== 'row'
  // On the headline link only, not the figure link beside it: both point at
  // the same article, and tagging both would let one card report two clicks.
  const attribution = {
    'data-nowb-entity': String(article.id),
    'data-nowb-entity-type': 'article',
    ...(rail && position !== undefined
      ? { 'data-nowb-rail': rail, 'data-nowb-position': String(position) }
      : {}),
  }

  const figure = withImage ? (
    <Link className="card__figure" href={href} tabIndex={-1} aria-hidden="true">
      <Image
        className="card__img"
        src={article.image}
        alt=""
        width={900}
        height={variant === 'portrait' ? 1125 : 600}
        sizes={variant === 'horizontal' || variant === 'rank' ? '220px' : '(max-width: 62rem) 50vw, 33vw'}
        priority={priority}
      />
    </Link>
  ) : null

  const headline = (
    <h3 className="card__headline display display--light">
      <Link href={href} {...attribution}>
        {article.title}
      </Link>
    </h3>
  )

  const foot = (
    <div className="card__foot">
      <Link className="card__section" href={`/${section}`}>
        {sectionLabel(section)}
      </Link>
      <span className="sep">·</span>
      <time dateTime={article.date}>{formatDate(article.date, locale, timeZone)}</time>
      {variant === 'standard' ? (
        <>
          <span className="sep">·</span>
          <span>{readingTime(article.paras)} min</span>
        </>
      ) : null}
      {partner ? <PartnerBadge /> : null}
    </div>
  )

  // `row` — Latest's index (§2, §3): no thumbnail, the date pinned to the far
  // right of the row rather than folded into the meta line, because a
  // three-column index needs every row's date to line up at a glance.
  if (variant === 'row') {
    return (
      <article className="card card--row">
        <h3 className="card__headline display display--light">
          <Link href={href} {...attribution}>
            {article.title}
          </Link>
        </h3>
        <span className="card--row__meta">
          <Link className="card__section" href={`/${section}`}>
            {sectionLabel(section)}
          </Link>
          <time className="card--row__date" dateTime={article.date}>
            {formatDate(article.date, locale, timeZone)}
          </time>
        </span>
      </article>
    )
  }

  // `rank` — the franchise band (§2): an oversized numeral, the headline,
  // and one portrait thumbnail, set for `--ink`. The numeral is display type
  // for the same reason a card headline is: this is one of the two places on
  // the reader site display type carries a number rather than a word.
  if (variant === 'rank') {
    return (
      <article className="card card--rank">
        {index !== undefined ? (
          <span className="card--rank__num display display--light" aria-hidden="true">
            {String(index).padStart(2, '0')}
          </span>
        ) : null}
        <div className="card--rank__body">
          {headline}
          <div className="card--rank__foot">
            <time dateTime={article.date}>{formatDate(article.date, locale, timeZone)}</time>
            {partner ? <PartnerBadge /> : null}
          </div>
        </div>
        {figure}
      </article>
    )
  }

  return (
    <article className={`card${variant === 'standard' ? '' : ` card--${variant}`}`}>
      {variant === 'index' && index !== undefined ? (
        <span className="card__num display display--light" aria-hidden="true">
          {String(index).padStart(2, '0')}
        </span>
      ) : null}

      {figure}

      <div className="card__body">
        {headline}
        {showDek && variant !== 'index' ? <p className="card__dek">{article.dek}</p> : null}
        {foot}
      </div>
    </article>
  )
}
