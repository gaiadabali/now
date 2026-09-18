import 'server-only'
import { query } from './db'

/**
 * Every read the console makes, in one file.
 *
 * Kept together rather than scattered through page components so that the
 * shape of what this tool touches is reviewable at a glance — this is the
 * commerce surface, and "what can the console see" should not require
 * grepping the app directory to answer.
 *
 * All SQL is parameterised. None of these take free text today, but the
 * habit is the point: the search filter below is the first place a string
 * from a URL reaches a query.
 */

export type Site = { id: string; slug: string; name: string; hostname: string | null }

export type OrgRow = {
  id: string
  name: string
  slug: string
  website: string | null
  type: string | null
  type_guess: string | null
  confidence: string | null
  partnership_count: number
  active_partnerships: number
}

export type PartnershipRow = {
  id: string
  tier: string | null
  status: string | null
  starts_at: string | null
  ends_at: string | null
  place_id: string | null
  site_slug: string | null
  show_badge: boolean | null
  is_live: boolean
}

/**
 * `engine.sites`, exactly as the row holds it — the four jsonb columns
 * un-shape-checked. `lib/site.ts`'s validators decide what any of this
 * *means* to a reader; this is the platform console's raw material for S5.1,
 * kept in this file rather than in `site.ts` because `site.ts` is the reader
 * app's typed contract (`SiteConfig`) and a console listing is not that — it
 * needs to show a malformed or `{}` value as itself, not merged with a
 * fallback.
 */
export type RegistrySite = {
  id: string
  slug: string
  name: string
  hostname: string
  status: string
  nav: unknown
  brand_tokens: unknown
  home_rails: unknown
  ranking_weights: unknown
  updated_at: string
}

export async function listRegistrySites(): Promise<RegistrySite[]> {
  return query<RegistrySite>(
    `SELECT id::text, slug, name, hostname, status, nav, brand_tokens, home_rails, ranking_weights,
            updated_at::text
       FROM engine.sites
      ORDER BY slug`,
  )
}

export async function getRegistrySite(slug: string): Promise<RegistrySite | null> {
  const rows = await query<RegistrySite>(
    `SELECT id::text, slug, name, hostname, status, nav, brand_tokens, home_rails, ranking_weights,
            updated_at::text
       FROM engine.sites
      WHERE slug = $1`,
    [slug],
  )
  return rows[0] ?? null
}

/**
 * The three writes S5.1 exposes. Each takes the already-validated value —
 * `team-editor/platform/sites/[slug]/actions.ts` runs it through `lib/site.ts`'s
 * `navFrom` / `brandTokensFrom` / `railsFrom` first, so by the time SQL sees
 * it, it is exactly what a reader would accept. `ranking_weights` has no write
 * here: nothing in this app reads that column yet (`lib/site.ts`'s `SiteConfig`
 * has no field for it), and a form that edits a value nothing observes is a
 * console screen that lies about having an effect.
 *
 * Each writes the WHOLE column: this is "replace the governed nav with this
 * one", not a merge, matching how `getSiteConfig()` reads it — a partial nav
 * would leave old items behind with no way to see them again from this
 * screen.
 */
export async function updateSiteNav(slug: string, nav: unknown): Promise<void> {
  await query(`UPDATE engine.sites SET nav = $1::jsonb, updated_at = now() WHERE slug = $2`, [
    JSON.stringify(nav),
    slug,
  ])
}

export async function updateSiteBrandTokens(slug: string, brandTokens: unknown): Promise<void> {
  await query(`UPDATE engine.sites SET brand_tokens = $1::jsonb, updated_at = now() WHERE slug = $2`, [
    JSON.stringify(brandTokens),
    slug,
  ])
}

export async function updateSiteHomeRails(slug: string, homeRails: unknown): Promise<void> {
  await query(`UPDATE engine.sites SET home_rails = $1::jsonb, updated_at = now() WHERE slug = $2`, [
    JSON.stringify(homeRails),
    slug,
  ])
}

export type CampaignRow = {
  id: string
  objective: string | null
  budget: string | null
  pacing: string | null
  status: string | null
  site_slug: string | null
  org_name: string | null
  placement_count: number
}

export async function listSites(): Promise<Site[]> {
  return query<Site>(
    `SELECT id::text, slug, name, hostname FROM engine.sites ORDER BY slug`,
  )
}

export async function countOrgs(): Promise<number> {
  const [row] = await query<{ n: string }>(`SELECT count(*)::text AS n FROM engine.orgs`)
  return Number(row?.n ?? 0)
}

/**
 * Orgs with their partnership counts.
 *
 * `active_partnerships` is computed from the dates here rather than trusting
 * `status` alone: ARCHITECTURE.md §11 resolves link policy from the *current*
 * partnership, and E4.1 proved expiry at query time. A row whose `ends_at`
 * has passed is not live no matter what its status column says, and a console
 * that showed otherwise would be lying about what the renderer will do.
 */
export async function listOrgs(search?: string, limit = 100): Promise<OrgRow[]> {
  const params: unknown[] = []
  let where = ''
  if (search && search.trim()) {
    params.push(`%${search.trim()}%`)
    where = `WHERE o.name ILIKE $1 OR o.slug ILIKE $1`
  }
  params.push(limit)
  return query<OrgRow>(
    `SELECT o.id::text,
            o.name,
            o.slug,
            o.website,
            o.type,
            o.type_guess,
            o.confidence::text,
            count(p.id)::int AS partnership_count,
            count(p.id) FILTER (
              WHERE p.status = 'active'
                AND (p.starts_at IS NULL OR p.starts_at <= now())
                AND (p.ends_at   IS NULL OR p.ends_at   >  now())
            )::int AS active_partnerships
       FROM engine.orgs o
       LEFT JOIN engine.partnerships p ON p.org_id = o.id
       ${where}
      GROUP BY o.id
      ORDER BY active_partnerships DESC, partnership_count DESC, o.name
      LIMIT $${params.length}`,
    params,
  )
}

export async function getOrg(id: string): Promise<OrgRow | null> {
  const rows = await query<OrgRow>(
    `SELECT o.id::text, o.name, o.slug, o.website, o.type, o.type_guess,
            o.confidence::text,
            0 AS partnership_count, 0 AS active_partnerships
       FROM engine.orgs o WHERE o.id = $1::uuid`,
    [id],
  )
  return rows[0] ?? null
}

export async function listPartnerships(orgId: string): Promise<PartnershipRow[]> {
  return query<PartnershipRow>(
    `SELECT p.id::text,
            p.tier,
            p.status,
            p.starts_at::text,
            p.ends_at::text,
            p.place_id,
            s.slug AS site_slug,
            p.show_badge,
            (p.status = 'active'
             AND (p.starts_at IS NULL OR p.starts_at <= now())
             AND (p.ends_at   IS NULL OR p.ends_at   >  now())) AS is_live
       FROM engine.partnerships p
       LEFT JOIN engine.sites s ON s.id = p.site_id
      WHERE p.org_id = $1::uuid
      ORDER BY is_live DESC, p.ends_at DESC NULLS LAST`,
    [orgId],
  )
}

export async function listCampaigns(): Promise<CampaignRow[]> {
  return query<CampaignRow>(
    `SELECT c.id::text,
            c.objective,
            c.budget::text,
            c.pacing,
            c.status,
            s.slug AS site_slug,
            o.name AS org_name,
            count(pl.id)::int AS placement_count
       FROM engine.campaigns c
       LEFT JOIN engine.sites s ON s.id = c.site_id
       LEFT JOIN engine.orgs  o ON o.id = c.org_id
       LEFT JOIN engine.placements pl ON pl.campaign_id = c.id
      GROUP BY c.id, s.slug, o.name
      ORDER BY c.created_at DESC NULLS LAST
      LIMIT 200`,
  )
}
