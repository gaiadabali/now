import 'server-only'

import pg from 'pg'

import { getByIds, type Article } from '@/lib/content'
import { getSiteConfig } from '@/lib/site'

/**
 * `engine.saved_items` (docs/READER-IDENTITY.md, migration 0007) — the
 * bookmark DESIGN-SYSTEM.md §3 flagged as missing: "A 'Save' affordance with
 * no persistence behind it… `saved_items` exists and is empty." This module
 * is that write path.
 *
 * Platform-scoped, same as every other reader table (`lib/reader.ts`,
 * `lib/preferences.ts`): a person reads both cities, so the row lives in
 * `now_platform`, not the city database. But `entity_id` is a CITY article
 * id — it is only meaningful alongside the `site_id` it was saved under,
 * because Bali's article #42 and Jakarta's article #42 are unrelated rows in
 * two different Postgres databases. Every query here therefore joins
 * `engine.sites` and filters on THIS PROCESS's own `SITE_SLUG` (via
 * `getSiteConfig()`), never accepting a site as a parameter — the same
 * defence `lib/preferences.ts#savePrefs` uses for `user_profiles`, so a
 * save can never be attributed to a city other than the one that made the
 * request.
 */

let platformPool: pg.Pool | null = null

function pool(): pg.Pool {
  const url = process.env.PLATFORM_DATABASE_URI ?? process.env.PLATFORM_DATABASE_URL
  if (!url) throw new Error('PLATFORM_DATABASE_URI is not set')
  platformPool ??= new pg.Pool({ connectionString: url, max: 4, statement_timeout: 5_000 })
  return platformPool
}

const ENTITY_TYPE = 'article'

/** Has this reader already saved this article, on this city's site row? */
export async function isSaved(identityId: string, entityId: number | string): Promise<boolean> {
  const site = await getSiteConfig()
  const { rows } = await pool().query(
    `SELECT 1
       FROM engine.saved_items si
       JOIN engine.sites s ON s.id = si.site_id
      WHERE si.identity_id = $1::uuid
        AND s.slug = $2
        AND si.entity_type = $3
        AND si.entity_id = $4
      LIMIT 1`,
    [identityId, site.slug, ENTITY_TYPE, String(entityId)],
  )
  return rows.length > 0
}

/**
 * Idempotent by construction: `ON CONFLICT DO NOTHING` against the table's
 * own primary key (`identity_id, site_id, entity_type, entity_id`). A
 * doubled click, a retried form post, or two tabs saving the same story at
 * once all land on the one row the table already has room for — none of
 * them is an error.
 */
export async function saveArticle(identityId: string, entityId: number | string): Promise<void> {
  const site = await getSiteConfig()
  await pool().query(
    `INSERT INTO engine.saved_items (identity_id, site_id, entity_type, entity_id)
          SELECT $1::uuid, s.id, $3, $4 FROM engine.sites s WHERE s.slug = $2
     ON CONFLICT (identity_id, site_id, entity_type, entity_id) DO NOTHING`,
    [identityId, site.slug, ENTITY_TYPE, String(entityId)],
  )
}

/** Also idempotent — removing a row that is not there is not an error either. */
export async function unsaveArticle(identityId: string, entityId: number | string): Promise<void> {
  const site = await getSiteConfig()
  await pool().query(
    `DELETE FROM engine.saved_items si
      USING engine.sites s
     WHERE s.id = si.site_id
       AND si.identity_id = $1::uuid
       AND s.slug = $2
       AND si.entity_type = $3
       AND si.entity_id = $4`,
    [identityId, site.slug, ENTITY_TYPE, String(entityId)],
  )
}

export type SavedEntry = { entityId: number; savedAt: Date }

/**
 * This reader's saves on THIS city, newest first.
 *
 * Exported separately from `getSavedArticles` below because
 * `lib/recommend.ts#getForYou` wants exactly the ids and weights, not the
 * rendered `Article`s a dashboard panel needs — one query, two callers,
 * rather than a second copy of this SQL living in `recommend.ts`.
 */
export async function listSavedArticles(identityId: string, limit = 24): Promise<SavedEntry[]> {
  const site = await getSiteConfig()
  const { rows } = await pool().query<{ entity_id: string; created_at: Date }>(
    `SELECT si.entity_id, si.created_at
       FROM engine.saved_items si
       JOIN engine.sites s ON s.id = si.site_id
      WHERE si.identity_id = $1::uuid
        AND s.slug = $2
        AND si.entity_type = $3
      ORDER BY si.created_at DESC
      LIMIT $4`,
    [identityId, site.slug, ENTITY_TYPE, limit],
  )
  return rows
    .map((r) => ({ entityId: Number(r.entity_id), savedAt: r.created_at }))
    .filter((r) => Number.isFinite(r.entityId))
}

/** The dashboard's Saved panel: this reader's saves, newest first, resolved
 * to real (published) articles. `getByIds` (lib/content.ts) already drops an
 * id that no longer resolves — a since-unpublished save disappears from the
 * list rather than rendering a hole, the same rule `lib/content.ts#getByIds`
 * applies to an editor's home-page pins. */
export async function getSavedArticles(identityId: string, limit = 24): Promise<Article[]> {
  const saved = await listSavedArticles(identityId, limit)
  if (saved.length === 0) return []
  return getByIds(saved.map((s) => s.entityId))
}
