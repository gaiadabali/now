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
