/**
 * Facet vocabulary access across two databases.
 *
 * ARCHITECTURE.md §4/§5: the seeded taxonomy (type, subtype, location,
 * format, cuisine, vibe, occasion, audience, amenities, price_band, topic —
 * 267 terms) lives in `now_platform.engine.terms` / `now_platform.engine.facets`
 * (E1.4). Payload binds exactly one database per instance — the *city* DB —
 * so it cannot read that table through its own DB adapter without breaking
 * "Payload owns public, Alembic owns engine" (ARCHITECTURE.md §1 rule #2)
 * for a schema it doesn't even live in.
 *
 * CHOSEN APPROACH: a short-lived, explicitly read-only `pg` connection to
 * `PLATFORM_DATABASE_URI`, opened once at CMS boot (module load, before
 * `buildConfig` runs), used only to SELECT term/facet rows and build the
 * static `options` arrays for the facet `select` fields on Articles/Places.
 * The connection is closed immediately after the one query and never
 * reopened per-request.
 *
 * Why this over a synced read-only copy table in each city DB's `public`
 * schema (the alternative the ticket names):
 *   - A synced copy would need a sync job (cron/worker) that is out of this
 *     package's scope (E1.6 owns only engine/packages/cms/**) and would
 *     introduce a second source of truth that can silently drift from
 *     now_platform.engine.terms between syncs.
 *   - The vocabulary is small (267 terms) and changes rarely (a taxonomy
 *     edit, not a per-article edit), so "options are fixed for the lifetime
 *     of a running CMS process, refreshed on restart" is an acceptable
 *     trade-off — it costs one restart per taxonomy change, in exchange for
 *     zero extra moving parts and zero risk of a stale copy diverging from
 *     the canonical table.
 *   - It keeps the *write* path (which is the one the schema-ownership rule
 *     is protecting) untouched: this module only ever SELECTs, from a
 *     database this package does not own either half of.
 *
 * Honest limitation, documented rather than hidden: CMS boot needs network
 * access to now_platform once, at startup. If that DB is unreachable at
 * boot, we do NOT crash the whole CMS (an editor should still be able to
 * fix a typo in a title while the platform DB has a blip) — we log loudly
 * and boot with empty option lists, which makes the affected select fields
 * show no choices until the next restart. That is a real degradation, not
 * a silent one: `[cms] vocabulary unavailable` is printed to stderr and
 * `vocabularyLoadError` is exported so a health-check endpoint could surface it.
 *
 * A future iteration (tracked for E1.8 / a later wave, not this ticket)
 * could add a `payload generate:importmap`-time refresh command or a
 * "reload vocabulary" admin action instead of requiring a full restart.
 */

// `pg` is CJS-only and does not provide static named ESM exports, so it
// must be imported as a default and destructured — `import { Client } from
// 'pg'` fails under Node's ESM loader with "does not provide an export
// named 'Client'".
import pg from 'pg'
const { Client } = pg

export type TermOption = {
  label: string
  value: string
  parentSlug: string | null
  /**
   * `now_platform.engine.terms.id` (uuid) for this term. Added for E2.8 (the
   * classification review queue): a review row must carry the platform-DB
   * term id, not just the slug, so the write-back domain event lets
   * `engine-worker` upsert `engine.entity_terms` (keyed on
   * `entity_type, entity_id, term_id`) without a second lookup. Harmless
   * addition for every existing consumer (Articles/Places only ever read
   * `label`/`value`/`parentSlug`).
   */
  termId: string
}

export type VocabularyMap = Record<string, TermOption[]>

let vocabularyLoadError: string | null = null

export function getVocabularyLoadError(): string | null {
  return vocabularyLoadError
}

const EMPTY_VOCABULARY: VocabularyMap = {}

/**
 * Fetch every seeded term, grouped by facet key, from the platform DB.
 * Read-only: this function issues exactly one SELECT and never writes.
 */
export async function loadVocabulary(): Promise<VocabularyMap> {
  const connectionString = process.env.PLATFORM_DATABASE_URI

  if (!connectionString) {
    vocabularyLoadError =
      'PLATFORM_DATABASE_URI is not set — facet select fields will have no options. ' +
      'Set it to the read-only DSN for now_platform so Payload can fetch the seeded taxonomy.'
    console.error(`[cms] ${vocabularyLoadError}`)
    return EMPTY_VOCABULARY
  }

  const client = new Client({ connectionString, connectionTimeoutMillis: 5000 })

  try {
    await client.connect()
    const { rows } = await client.query<{
      facet_key: string
      term_id: string
      slug: string
      label: string
      parent_slug: string | null
    }>(
      `SELECT f.key AS facet_key, t.id AS term_id, t.slug, t.label, p.slug AS parent_slug
         FROM engine.terms t
         JOIN engine.facets f ON f.id = t.facet_id
         LEFT JOIN engine.terms p ON p.id = t.parent_id
        ORDER BY f.key, t.label`,
    )

    const vocabulary: VocabularyMap = {}
    for (const row of rows) {
      const bucket = (vocabulary[row.facet_key] ??= [])
      bucket.push({ label: row.label, value: row.slug, parentSlug: row.parent_slug, termId: row.term_id })
    }

    vocabularyLoadError = null
    console.log(
      `[cms] vocabulary loaded from platform DB: ${rows.length} terms across ${
        Object.keys(vocabulary).length
      } facets`,
    )
    return vocabulary
  } catch (err) {
    vocabularyLoadError = `failed to load vocabulary from PLATFORM_DATABASE_URI: ${
      err instanceof Error ? err.message : String(err)
    }`
    console.error(`[cms] ${vocabularyLoadError}`)
    return EMPTY_VOCABULARY
  } finally {
    await client.end().catch(() => {})
  }
}

/** Build Payload `select` options for one facet, defaulting to empty. */
export function optionsFor(vocabulary: VocabularyMap, facetKey: string): TermOption[] {
  return vocabulary[facetKey] ?? []
}
