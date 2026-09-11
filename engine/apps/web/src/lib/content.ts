/**
 * Fixture-backed content access — COMP PHASE ONLY.
 *
 * Every function here has the signature the real data layer will have, so
 * pages never change when the source does. The replacement is a Payload
 * Local API call against the city DB (`public` schema) plus engine-api for
 * the ranked rails (ARCHITECTURE.md §16) — see `docs/ui-data-layer.md`.
 */

import raw from '@/fixtures/articles.json'
import { slugify } from '@/lib/format'

export type Article = {
  id: number
  title: string
  slug: string
  date: string
  section: string
  categories: string[]
  tags: string[]
  image: string
  dek: string
  paras: string[]
  views: number
}

const ARTICLES = raw as Article[]

/** Editorial sections, in masthead order, mapped from legacy WP categories. */
const SECTION_MAP: Record<string, string[]> = {
  dining: ['Dining News', 'Restaurants and Bars', 'Dining Offers', 'Bar Guide', 'Food and Drink'],
  stay: ['Hotels & Resorts', 'Hotels and Resorts', 'Stay Offers', 'Accommodation'],
  culture: ['Culture', 'Myths and Legends', 'Dance and Music', 'Art', 'Community', 'Opinion'],
  wellness: ['Spa and Wellness', 'Wellness', 'Health'],
  'things-to-do': ['Activities', 'Explore Bali', 'Experience Offers', 'Shopping', 'Lifestyle', 'Reviews'],
}

export function sectionOf(article: Article): string {
  for (const [slug, cats] of Object.entries(SECTION_MAP)) {
    if (cats.includes(article.section)) return slug
  }
  return slugify(article.section)
}

export function isSectionSlug(slug: string): boolean {
  return slug in SECTION_MAP
}

export function sectionLabel(slug: string): string {
  return slug
    .split('-')
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(' ')
}

export async function getLatest(limit = 20): Promise<Article[]> {
  return ARTICLES.slice(0, limit)
}

export async function getLead(): Promise<Article> {
  return ARTICLES[0]
}

export async function getBySection(slug: string, limit = 12): Promise<Article[]> {
  return ARTICLES.filter((a) => sectionOf(a) === slug).slice(0, limit)
}

export async function getBySlug(slug: string): Promise<Article | undefined> {
  return ARTICLES.find((a) => a.slug === slug)
}

export async function getMostRead(limit = 5): Promise<Article[]> {
  return [...ARTICLES].sort((a, b) => b.views - a.views).slice(0, limit)
}

/**
 * Stand-in for the engine's related-content rail. The real implementation
 * calls `GET /v1/articles/{id}/rails`, which is already live.
 */
export async function getRelated(article: Article, limit = 3): Promise<Article[]> {
  return ARTICLES.filter((a) => a.id !== article.id && sectionOf(a) === sectionOf(article)).slice(0, limit)
}

/*
 * Comp-phase stand-ins for content the engine will supply. They live under
 * `src/fixtures/` so the site-literal guard treats them as sample data, not
 * as code that knows which city it serves.
 */
export { GUIDES, EVENTS, PLACE } from '@/fixtures/editorial'
