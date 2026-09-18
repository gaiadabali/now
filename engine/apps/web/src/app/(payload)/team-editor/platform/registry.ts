import { brandTokensFrom, navFrom, railsFrom } from '@/lib/site'
import type { HomeRail, NavItem, SiteConfig } from '@/lib/site'

/**
 * "Governed, or falling back to the file" — computed with the exact
 * predicates `getSiteConfig()` uses, not a description of them.
 *
 * This is the single most useful thing S5.1 asked this screen to show, and
 * the ticket that asked for it is explicit about why it has to be the reader's
 * own function: a console that approximates `navFrom` can disagree with it,
 * and the disagreement is invisible until an editor saves something the
 * approximation accepted and the real reader rejects. So `governed` here is
 * never re-derived — it is `navFrom(raw) !== null`, full stop.
 *
 * `emptyColumn` distinguishes two reasons a field falls back, for the
 * console's benefit only (the reader does not care): `{}`/`[]` means nobody
 * has touched this row, a non-empty-but-rejected value means someone (this
 * console, a script, a manual `UPDATE`) wrote something `navFrom`/`railsFrom`
 * refuses. Both read as "falling back" to a visitor of the site; an editor
 * looking at *why* benefits from knowing which one it is.
 */
export type ArrayFieldReport<T> = {
  raw: unknown
  governed: boolean
  /** What a reader actually gets for this field right now. */
  effective: T[] | null
  emptyColumn: boolean
}

export function navReport(raw: unknown): ArrayFieldReport<NavItem> {
  const effective = navFrom(raw)
  return { raw, governed: effective !== null, effective, emptyColumn: !Array.isArray(raw) || raw.length === 0 }
}

export function railsReport(raw: unknown): ArrayFieldReport<HomeRail> {
  const effective = railsFrom(raw)
  return { raw, governed: effective !== null, effective, emptyColumn: !Array.isArray(raw) || raw.length === 0 }
}

/**
 * `brand_tokens` has no wholesale valid/invalid verdict (see
 * `brandTokensFrom`'s own comment) — a row can govern `logo` and leave
 * `favicon` to the file, and that is correct, not partial failure. So
 * "governed" here means "at least one mark is set", and the per-field detail
 * is what the edit screen actually needs to show the side-by-side.
 */
export type BrandFieldReport = {
  raw: unknown
  governed: boolean
  fields: Partial<SiteConfig['brand']>
}

export function brandReport(raw: unknown): BrandFieldReport {
  const fields = brandTokensFrom(raw)
  return { raw, governed: Object.keys(fields).length > 0, fields }
}

/**
 * `ranking_weights` — governed/ungoverned only, with no reader semantics to
 * agree with: nothing in this app reads that column (`SiteConfig` has no
 * field for it), so there is no `rankingWeightsFrom` in `lib/site.ts` to
 * reuse and inventing one for a value nobody consumes would be a validator
 * with nothing to validate against. This mirrors `seed-site-registry.mjs`'s
 * own `isUngoverned` check — the column default is `{}`, so anything else is
 * "set", regardless of shape.
 */
export function jsonColumnGoverned(raw: unknown): boolean {
  if (raw === null || raw === undefined) return false
  if (typeof raw !== 'object') return false
  return Array.isArray(raw) ? raw.length > 0 : Object.keys(raw).length > 0
}
