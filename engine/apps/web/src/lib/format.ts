/** Presentation helpers. Locale and timezone always come from SiteConfig. */

export function formatDate(iso: string, locale: string, timeZone: string): string {
  return new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone,
  }).format(new Date(iso))
}

export function formatDay(iso: string, locale: string, timeZone: string) {
  const d = new Date(iso)
  return {
    day: new Intl.DateTimeFormat(locale, { day: 'numeric', timeZone }).format(d),
    month: new Intl.DateTimeFormat(locale, { month: 'short', timeZone }).format(d),
  }
}

/** 220 wpm — the usual magazine figure, rounded up to whole minutes. */
export function readingTime(paragraphs: string[]): number {
  const words = paragraphs.join(' ').split(/\s+/).filter(Boolean).length
  return Math.max(1, Math.ceil(words / 220))
}

export function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}


/**
 * Counts, grouped the way an English reader expects.
 *
 * NOT `toLocaleString(site.locale)`. The sites are `en-ID` — English, written
 * in Indonesia — and Intl applies the REGION's numbering to that, so 4429
 * comes out "4.429". In English editorial copy that reads as a decimal: "one
 * thing worth rereading from the 4.429 stories behind us" says four-point-
 * four-two-nine. Dates and currency should follow the locale, because those
 * are local conventions a reader here expects; digit grouping in an English
 * sentence is not.
 *
 * One helper so this cannot drift again — the same page had `en` in one place
 * and `site.locale` in another.
 */
export function formatCount(value: number): string {
  return value.toLocaleString('en')
}

/**
 * Every spelling one address can arrive in.
 *
 * WordPress stored non-ASCII permalinks percent-encoded in LOWER case
 * (`kita-%e5%96%9c%e5%a4%9a-restaurant-…`), and the S1.1 backfill copied them
 * into `slug` verbatim. Next hands the route param over DECODED (`kita-喜多-…`),
 * so an exact match never met the stored form and three legacy addresses —
 * one Bali, two Jakarta, found by requesting every venue story on the
 * production build — returned 404. Old addresses are the search traffic, so
 * both spellings are tried: as given, and re-encoded the way WordPress wrote it.
 */
export function slugForms(slug: string): string[] {
  let decoded = slug
  try {
    decoded = decodeURIComponent(slug)
  } catch {
    // A stray '%' that is not an escape: keep the address as it came.
  }
  const wordpress = encodeURIComponent(decoded).replace(/%[0-9A-F]{2}/g, (escape) => escape.toLowerCase())
  return Array.from(new Set([slug, decoded, wordpress]))
}
