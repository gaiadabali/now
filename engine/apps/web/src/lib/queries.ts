import 'server-only'
import { db, query } from './db'
import { cityPool } from './payload'

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

export type Site = { id: string; slug: string; name: string; hostname: string | null; locale: string }

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
  /**
   * From the one-time outbound-link scan (E1.5, `packages/partner-roster`)
   * that seeded this org in the first place — how many archive articles
   * link to one of `domains` and how many links that adds up to. Real,
   * stored figures, not computed on this query: `article_count` is a
   * snapshot from whenever the roster last ran, not a live count, and is
   * `null` for an org this console created rather than the roster (it was
   * never part of that scan). Shown on the blast-radius screen as the one
   * piece of REAL commercial exposure a brand-new partnership already has,
   * even before any venue is linked to it — see `computeBlastRadius`.
   */
  article_count: number | null
  link_count: number | null
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
    `SELECT id::text, slug, name, hostname, locale FROM engine.sites ORDER BY slug`,
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
            o.confidence::text, o.article_count, o.link_count,
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

/* ------------------------------------------------------------------------
 * S5.2 — the partnership write path.
 *
 * ARCHITECTURE.md §11's one screen: org, tier, status, contract dates, link
 * policy, custom URL, UTM template, badge, itinerary eligibility, boost cap
 * — plus the linked mention count (blast radius, S5.3, further down). Every
 * write here goes through `createPartnership`/`updatePartnership`, and both
 * insert a `partnership_audit` row in the SAME transaction as the data write
 * — never a follow-up statement, so a crash between the two can only ever
 * leave the database exactly as it was before either ran.
 *
 * **`partnership_audit.actor_id` is `uuid`, with no foreign key, and
 * `public.users.id` is a Payload-assigned `integer` sequence.** A real
 * mismatch, not glossed over: there is no value this file can put in that
 * column that both fits its type and means anything back to a staff row.
 * Rather than inventing an unexplained integer→uuid encoding to force a
 * column to hold something it cannot really carry, `actor_id` is left NULL
 * and the actor is named in `after` instead, under a reserved `_audit` key
 * (`auditStamp` below) — human-readable, queryable with a plain `->>`, and
 * honest about why the "proper" column is empty. See this file's report to
 * the orchestrator for the migration this points at
 * (`actor_email text`) — out of scope here (no Alembic migrations without
 * sign-off; see AGENTS instructions).
 * ---------------------------------------------------------------------- */

export type PartnershipTier = 'free' | 'listed' | 'paid'
export type PartnershipStatus = 'active' | 'paused' | 'ended'

/**
 * Deliberately no `linkPolicy` field here. The column (`engine.partnerships
 * .link_policy`, `jsonb not null default '{}'`) stays exactly as it is —
 * this console never sets it, on create or on edit — because
 * `now_link_resolver` (the code that decides what a reader actually sees)
 * does not read it: tier alone decides the sponsored link and the badge.
 * A form editing a value nothing consumes is a screen that lies about
 * having an effect (docs/SURFACES-PLAN.md §7's own rule), so it is not a
 * field here at all rather than a field that quietly does nothing.
 */
export type PartnershipWritable = {
  tier: PartnershipTier
  status: PartnershipStatus
  startsAt: string | null
  endsAt: string | null
  customUrl: string | null
  utmTemplate: string | null
  showBadge: boolean
  badgeLabel: string | null
  itineraryEligible: boolean
  boostCap: number | null
}

export type NewPartnershipInput = PartnershipWritable & {
  siteId: string
  orgId: string | null
  placeId: string | null
}

export type PartnershipDetail = PartnershipWritable & {
  id: string
  orgId: string | null
  placeId: string | null
  siteId: string
  siteSlug: string
  orgName: string | null
  createdAt: string
  updatedAt: string
}

export type Actor = { id: number; email: string }

type PartnershipRawRow = {
  id: string
  org_id: string | null
  place_id: string | null
  site_id: string
  tier: PartnershipTier
  status: PartnershipStatus
  starts_at: string | null
  ends_at: string | null
  link_policy: Record<string, unknown>
  custom_url: string | null
  utm_template: string | null
  show_badge: boolean
  badge_label: string | null
  itinerary_eligible: boolean
  boost_cap: string | null
  created_at: string
  updated_at: string
}

const PARTNERSHIP_RETURNING = `
  id::text, org_id::text AS org_id, place_id, site_id::text AS site_id, tier, status,
  starts_at::text, ends_at::text, link_policy, custom_url, utm_template,
  show_badge, badge_label, itinerary_eligible, boost_cap::text,
  created_at::text, updated_at::text`

/**
 * Same projection, column-qualified. Needed only by `updatePartnership`'s
 * `UPDATE ... FROM engine.sites s ...` below — with a second table in scope,
 * an unqualified `status` (both `engine.partnerships` and `engine.sites`
 * have one) is ambiguous and Postgres refuses the query outright. Kept as
 * its own literal list rather than derived from `PARTNERSHIP_RETURNING` by
 * string surgery, which is exactly the kind of "looks right, silently wrong"
 * code this file's own comments elsewhere warn against.
 */
const PARTNERSHIP_RETURNING_QUALIFIED = `
  p.id::text, p.org_id::text AS org_id, p.place_id, p.site_id::text AS site_id, p.tier, p.status,
  p.starts_at::text, p.ends_at::text, p.link_policy, p.custom_url, p.utm_template,
  p.show_badge, p.badge_label, p.itinerary_eligible, p.boost_cap::text,
  p.created_at::text, p.updated_at::text`

function rawFields(row: PartnershipRawRow) {
  return {
    orgId: row.org_id,
    placeId: row.place_id,
    siteId: row.site_id,
    tier: row.tier,
    status: row.status,
    startsAt: row.starts_at,
    endsAt: row.ends_at,
    customUrl: row.custom_url,
    utmTemplate: row.utm_template,
    showBadge: row.show_badge,
    badgeLabel: row.badge_label,
    itineraryEligible: row.itinerary_eligible,
    boostCap: row.boost_cap === null ? null : Number(row.boost_cap),
  }
}

/**
 * The one shape every audit row's `after` carries. Never in `before` — a
 * prior state was not authored by the actor making THIS write, only the new
 * one was, so naming an actor against history they did not create would be
 * backdating attribution. `before` is always a plain field snapshot (or
 * `null` on create); read `after._audit` to answer "who did this."
 */
function auditStamp(actor: Actor, fields: ReturnType<typeof rawFields>) {
  return { _audit: { actorId: actor.id, actorEmail: actor.email }, ...fields }
}

function toDetail(row: PartnershipRawRow, siteSlug: string, orgName: string | null): PartnershipDetail {
  return {
    id: row.id,
    siteSlug,
    orgName,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    ...rawFields(row),
  }
}

export async function getPartnership(id: string): Promise<PartnershipDetail | null> {
  const rows = await query<PartnershipRawRow & { site_slug: string; org_name: string | null }>(
    `SELECT p.id::text, p.org_id::text AS org_id, p.place_id, p.site_id::text AS site_id, p.tier,
            p.status, p.starts_at::text, p.ends_at::text, p.link_policy, p.custom_url,
            p.utm_template, p.show_badge, p.badge_label, p.itinerary_eligible, p.boost_cap::text,
            p.created_at::text, p.updated_at::text,
            s.slug AS site_slug, o.name AS org_name
       FROM engine.partnerships p
       JOIN engine.sites s ON s.id = p.site_id
       LEFT JOIN engine.orgs o ON o.id = p.org_id
      WHERE p.id = $1::uuid`,
    [id],
  )
  const row = rows[0]
  return row ? toDetail(row, row.site_slug, row.org_name) : null
}

export type PartnershipAuditRow = {
  id: string
  ts: string
  before: (ReturnType<typeof rawFields> & { _audit?: { actorId: number; actorEmail: string } }) | null
  after: ReturnType<typeof rawFields> & { _audit: { actorId: number; actorEmail: string } }
}

export async function listPartnershipAudit(partnershipId: string): Promise<PartnershipAuditRow[]> {
  return query<PartnershipAuditRow>(
    `SELECT id::text, ts::text, before, after
       FROM engine.partnership_audit
      WHERE partnership_id = $1::uuid
      ORDER BY ts DESC`,
    [partnershipId],
  )
}

/**
 * Create a partnership and its opening audit row in one transaction.
 *
 * `site_id`, `org_id` and `place_id` are write-once: set here, never
 * mutated by `updatePartnership` below. That is a deliberate simplification,
 * not an oversight — it is what makes `canWritePartnershipForSite`'s
 * site-scoping check sound. If a site could be changed after creation, a
 * `partner_manager` scoped to their own city could create a row there and
 * then edit it to point at another city's site, which no per-write scope
 * check would catch without re-deriving it from a value the request itself
 * supplied. Moving a partnership to another site is not a feature this
 * ticket builds.
 */
export async function createPartnership(input: NewPartnershipInput, actor: Actor): Promise<PartnershipDetail> {
  const client = await db().connect()
  try {
    await client.query('BEGIN')
    // No `link_policy` column here — it keeps its `'{}'::jsonb` default.
    // See `PartnershipWritable`'s own comment for why this console never
    // sets it.
    const inserted = await client.query<PartnershipRawRow>(
      `INSERT INTO engine.partnerships
         (org_id, place_id, site_id, tier, status, starts_at, ends_at,
          custom_url, utm_template, show_badge, badge_label, itinerary_eligible, boost_cap)
       VALUES ($1::uuid, $2, $3::uuid, $4, $5, $6::timestamptz, $7::timestamptz,
               $8, $9, $10, $11, $12, $13::numeric)
       RETURNING ${PARTNERSHIP_RETURNING}`,
      [
        input.orgId,
        input.placeId,
        input.siteId,
        input.tier,
        input.status,
        input.startsAt,
        input.endsAt,
        input.customUrl,
        input.utmTemplate,
        input.showBadge,
        input.badgeLabel,
        input.itineraryEligible,
        input.boostCap,
      ],
    )
    const row = inserted.rows[0]
    await client.query(
      `INSERT INTO engine.partnership_audit (partnership_id, actor_id, before, after)
       VALUES ($1::uuid, NULL, NULL, $2::jsonb)`,
      [row.id, JSON.stringify(auditStamp(actor, rawFields(row)))],
    )
    await client.query('COMMIT')
    const site = await query<{ slug: string }>(`SELECT slug FROM engine.sites WHERE id = $1::uuid`, [row.site_id])
    const org = row.org_id
      ? await query<{ name: string }>(`SELECT name FROM engine.orgs WHERE id = $1::uuid`, [row.org_id])
      : []
    return toDetail(row, site[0]?.slug ?? input.siteId, org[0]?.name ?? null)
  } catch (error) {
    await client.query('ROLLBACK')
    throw error
  } finally {
    client.release()
  }
}

export type UpdatePartnershipResult =
  | { ok: true; partnership: PartnershipDetail }
  | { ok: false; reason: 'not_found_or_out_of_scope' }

/**
 * Update a partnership and its audit row in one transaction.
 *
 * **`scope` is enforced in the `UPDATE`'s own `WHERE` clause, not only in
 * application code above this function.** `'any'` for a commerce admin,
 * otherwise the one site slug a `partner_manager` may touch
 * (`commerceCurrentSiteSlug()`, `lib/auth.ts`). If the row's site does not
 * match, `rowCount` is 0 and nothing — not the partnership, not an audit
 * row — is written; the caller cannot tell "does not exist" apart from
 * "exists but is out of scope", which is the same information-hiding
 * `requirePartnershipWriteAccess` already applies one layer up. Two
 * independent checks of the same rule (the action's gate, and this SQL
 * WHERE clause) is the point: a bug in one is not a bypass of the other.
 */
export async function updatePartnership(
  id: string,
  patch: PartnershipWritable,
  actor: Actor,
  scope: string,
): Promise<UpdatePartnershipResult> {
  const client = await db().connect()
  try {
    await client.query('BEGIN')

    const beforeRes = await client.query<PartnershipRawRow & { site_slug: string }>(
      `SELECT p.id::text, p.org_id::text AS org_id, p.place_id, p.site_id::text AS site_id, p.tier,
              p.status, p.starts_at::text, p.ends_at::text, p.link_policy, p.custom_url,
              p.utm_template, p.show_badge, p.badge_label, p.itinerary_eligible, p.boost_cap::text,
              p.created_at::text, p.updated_at::text, s.slug AS site_slug
         FROM engine.partnerships p
         JOIN engine.sites s ON s.id = p.site_id
        WHERE p.id = $1::uuid
        FOR UPDATE`,
      [id],
    )
    const before = beforeRes.rows[0]
    if (!before) {
      await client.query('ROLLBACK')
      return { ok: false, reason: 'not_found_or_out_of_scope' }
    }

    // No `link_policy` in the SET list — this console never wrote it (see
    // `PartnershipWritable`'s comment), so an edit leaves the column exactly
    // as it was, rather than re-writing it back to itself for no reason.
    const updateRes = await client.query<PartnershipRawRow>(
      `UPDATE engine.partnerships p
          SET tier = $3, status = $4, starts_at = $5::timestamptz, ends_at = $6::timestamptz,
              custom_url = $7, utm_template = $8, show_badge = $9,
              badge_label = $10, itinerary_eligible = $11, boost_cap = $12::numeric, updated_at = now()
         FROM engine.sites s
        WHERE p.id = $1::uuid AND p.site_id = s.id AND ($2 = 'any' OR s.slug = $2)
        RETURNING ${PARTNERSHIP_RETURNING_QUALIFIED}`,
      [
        id,
        scope,
        patch.tier,
        patch.status,
        patch.startsAt,
        patch.endsAt,
        patch.customUrl,
        patch.utmTemplate,
        patch.showBadge,
        patch.badgeLabel,
        patch.itineraryEligible,
        patch.boostCap,
      ],
    )

    if (updateRes.rowCount === 0) {
      await client.query('ROLLBACK')
      return { ok: false, reason: 'not_found_or_out_of_scope' }
    }
    const after = updateRes.rows[0]

    await client.query(
      `INSERT INTO engine.partnership_audit (partnership_id, actor_id, before, after)
       VALUES ($1::uuid, NULL, $2::jsonb, $3::jsonb)`,
      [id, JSON.stringify(rawFields(before)), JSON.stringify(auditStamp(actor, rawFields(after)))],
    )
    await client.query('COMMIT')

    const org = after.org_id
      ? await query<{ name: string }>(`SELECT name FROM engine.orgs WHERE id = $1::uuid`, [after.org_id])
      : []
    return { ok: true, partnership: toDetail(after, before.site_slug, org[0]?.name ?? null) }
  } catch (error) {
    await client.query('ROLLBACK')
    throw error
  } finally {
    client.release()
  }
}

/* ------------------------------------------------------------------------
 * S5.3 — blast radius, computed from real data before a write commits.
 *
 * "This affects 40 articles across 3 venues" (ARCHITECTURE.md §11) means
 * counting `place_mentions` rows in the CITY database — `engine.orgs` and
 * `engine.partnerships` are platform-wide, but which articles mention a
 * place is per-city content, reachable only through `cityPool()`
 * (`lib/payload.ts`), which is bound to whichever single city this process
 * serves (`DATABASE_URI` — ARCHITECTURE.md §3.5's "one deliberate per-city
 * knob"). A partnership can target ANY registered site — commerce is
 * platform-wide and visible from both cities' admin sessions
 * (docs/ADMIN-CONSOLIDATION.md) — but this process can only ever count ITS
 * OWN city's mentions. Exactly `facetCoverage.ts`'s honesty problem, and
 * this follows the same rule: report the real number for a matching site,
 * and say plainly why there is none for any other.
 * ---------------------------------------------------------------------- */

function plural(n: number, one: string, many: string): string {
  return `${n.toLocaleString()} ${n === 1 ? one : many}`
}

export type BlastRadius = {
  /** Whether this process's own city database could answer the question. */
  computable: boolean
  citySlug: string
  targetSiteSlug: string
  /** Articles that mention one of this organisation's LINKED venues. */
  articleCount: number
  /** How many of those linked venues are actually mentioned. */
  venueCount: number
  /**
   * How many venues in this city are linked to this organisation at all,
   * mentioned or not — the real reason `articleCount` is so often zero.
   * `places.org_id` is NULL on every single row in both cities today (5,918
   * in Bali, 6,589 in Jakarta) even though both cities together carry over
   * 21,000 real `place_mentions` rows — the mentions exist, nothing has ever
   * pointed a venue at an organisation. That is what "Venues belonging to
   * this organisation" on the org screen exists to fix.
   */
  linkedVenueCount: number
  /**
   * `engine.orgs.article_count` — real exposure this organisation already
   * has, independent of any venue link: how many archive articles once
   * linked out to its own website. A one-time figure from when the roster
   * was built, not computed on this request — `null` for an org the roster
   * never saw (one created directly in this console, for instance).
   */
  orgArticleLinkCount: number | null
  note: string
}

export async function computeBlastRadius(params: {
  orgId: string | null
  placeId: string | null
  targetSiteSlug: string
  /** From `getOrg()` — passed in rather than re-queried here. */
  orgArticleLinkCount?: number | null
}): Promise<BlastRadius> {
  const citySlug = process.env.SITE_SLUG ?? ''
  const orgArticleLinkCount = params.orgArticleLinkCount ?? null

  if (params.targetSiteSlug !== citySlug) {
    return {
      computable: false,
      citySlug,
      targetSiteSlug: params.targetSiteSlug,
      articleCount: 0,
      venueCount: 0,
      linkedVenueCount: 0,
      orgArticleLinkCount,
      note:
        `This partnership is for ${params.targetSiteSlug}, and this screen is signed in to ` +
        `${citySlug || 'a different site'}. Sign in to ${params.targetSiteSlug}'s own admin to see what it affects there.`,
    }
  }

  if (params.orgId) {
    const { rows } = await cityPool().query<{ linked: string; mentioned_venues: string; articles: string }>(
      `SELECT count(pl.id) AS linked,
              count(DISTINCT pm.place_id) AS mentioned_venues,
              count(DISTINCT pm.article_id) AS articles
         FROM public.places pl
         LEFT JOIN public.place_mentions pm ON pm.place_id = pl.id
        WHERE pl.org_id = $1`,
      [params.orgId],
    )
    const linkedVenueCount = Number(rows[0]?.linked ?? 0)
    const venueCount = Number(rows[0]?.mentioned_venues ?? 0)
    const articleCount = Number(rows[0]?.articles ?? 0)

    let note: string
    if (linkedVenueCount === 0) {
      note =
        'No venue is linked to this organisation yet, so this partnership changes nothing on the ' +
        'site until one is. Link a venue below, under "Venues belonging to this organisation."'
    } else if (articleCount === 0) {
      note = `${plural(linkedVenueCount, 'venue is', 'venues are')} linked to this organisation, but no article currently mentions ${linkedVenueCount === 1 ? 'it' : 'any of them'}.`
    } else {
      note = `${plural(articleCount, 'article mentions', 'articles mention')} ${plural(venueCount, 'venue', 'venues')} belonging to this organisation, in ${citySlug}.`
    }

    return { computable: true, citySlug, targetSiteSlug: params.targetSiteSlug, articleCount, venueCount, linkedVenueCount, orgArticleLinkCount, note }
  }

  if (params.placeId) {
    const { rows } = await cityPool().query<{ articles: string }>(
      `SELECT count(DISTINCT pm.article_id) AS articles
         FROM public.place_mentions pm
         JOIN public.places pl ON pl.id = pm.place_id
        WHERE pl.id::text = $1`,
      [params.placeId],
    )
    const articleCount = Number(rows[0]?.articles ?? 0)
    return {
      computable: true,
      citySlug,
      targetSiteSlug: params.targetSiteSlug,
      articleCount,
      venueCount: articleCount > 0 ? 1 : 0,
      linkedVenueCount: 1,
      orgArticleLinkCount: null,
      note:
        articleCount === 0
          ? `No article in ${citySlug} currently mentions this place.`
          : `${plural(articleCount, 'article mentions', 'articles mention')} this place in ${citySlug}.`,
    }
  }

  return {
    computable: true,
    citySlug,
    targetSiteSlug: params.targetSiteSlug,
    articleCount: 0,
    venueCount: 0,
    linkedVenueCount: 0,
    orgArticleLinkCount,
    note: 'Neither an organisation nor a place is set yet.',
  }
}

/* ------------------------------------------------------------------------
 * Venues linked to an organisation — what makes a partnership do anything.
 *
 * `places.org_id` is empty on every one of both cities' real rows today
 * (5,918 in Bali, 6,589 in Jakarta) — not because venues aren't mentioned
 * in articles (over 21,000 real `place_mentions` rows across both cities
 * say otherwise) but because nothing has ever written to this column.
 * These are READS only — plain SQL against `cityPool()`, matching every
 * other read in this file. The WRITE (setting `places.org_id`) goes
 * through Payload's Local API instead, in
 * `commerce/orgs/[id]/venuesActions.ts` — a city collection with its own
 * hooks and version history should be written the way its own admin
 * writes it, not by a second, parallel SQL path that skips both.
 * ---------------------------------------------------------------------- */

export type CityPlace = { id: string; name: string; slug: string; type: string | null; orgId: string | null }

function toCityPlace(row: { id: string; name: string; slug: string; type: string | null; org_id: string | null }): CityPlace {
  return { id: row.id, name: row.name, slug: row.slug, type: row.type, orgId: row.org_id }
}

export async function listOrgVenues(orgId: string): Promise<CityPlace[]> {
  const { rows } = await cityPool().query<{ id: string; name: string; slug: string; type: string | null; org_id: string | null }>(
    `SELECT id::text, name, slug, type::text, org_id FROM public.places WHERE org_id = $1 ORDER BY name`,
    [orgId],
  )
  return rows.map(toCityPlace)
}

/** Search this city's places by name — the picker for "attach a venue". */
export async function searchCityPlaces(term: string, limit = 20): Promise<CityPlace[]> {
  const trimmed = term.trim()
  if (!trimmed) return []
  const { rows } = await cityPool().query<{ id: string; name: string; slug: string; type: string | null; org_id: string | null }>(
    `SELECT id::text, name, slug, type::text, org_id
       FROM public.places
      WHERE name ILIKE $1
      ORDER BY name
      LIMIT $2`,
    [`%${trimmed}%`, limit],
  )
  return rows.map(toCityPlace)
}
