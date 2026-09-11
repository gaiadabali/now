import Image from 'next/image'
import Link from 'next/link'

import { PartnerBadge } from '@/components/primitives'
import type { Article } from '@/lib/content'
import { sectionOf, sectionLabel } from '@/lib/content'
import { formatDate, readingTime } from '@/lib/format'

type Variant = 'standard' | 'portrait' | 'horizontal' | 'index'

/**
 * The single story card for the whole site. One component, four variants —
 * a second card component is how design systems start to rot, so new needs
 * become a variant here or they do not exist.
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
}: {
  article: Article
  variant?: Variant
  index?: number
  showDek?: boolean
  partner?: boolean
  locale: string
  timeZone: string
  priority?: boolean
}) {
  const section = sectionOf(article)
  const href = `/${article.slug}`
  const withImage = variant !== 'index'

  return (
    <article className={`card${variant === 'standard' ? '' : ` card--${variant}`}`}>
      {variant === 'index' && index !== undefined ? (
        <span className="card__num" aria-hidden="true">
          {String(index).padStart(2, '0')}
        </span>
      ) : null}

      {withImage ? (
        <Link className="card__figure" href={href} tabIndex={-1} aria-hidden="true">
          <Image
            className="card__img"
            src={article.image}
            alt=""
            width={900}
            height={600}
            sizes={variant === 'horizontal' ? '220px' : '(max-width: 62rem) 50vw, 33vw'}
            priority={priority}
          />
        </Link>
      ) : null}

      <div className="card__body">
        <h3 className="card__headline display">
          <Link href={href}>{article.title}</Link>
        </h3>

        {showDek && variant !== 'index' ? <p className="card__dek">{article.dek}</p> : null}

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
      </div>
    </article>
  )
}
