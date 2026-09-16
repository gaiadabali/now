/**
 * Backfill `_articles_v` so the archive is visible in the team editor.
 *
 *   npm run backfill:article-versions                    # dry run, reports
 *   BACKFILL_APPLY=1 npm run backfill:article-versions   # writes
 *   BACKFILL_LIMIT=20 npm run backfill:article-versions  # first N only
 *
 * Configured by environment, not flags, because `payload run` does not pass
 * argv through to the script — `process.argv.slice(2)` is `[]` however the
 * command is spelled, so a `--apply` flag would be silently ignored and a
 * dry run would look like a successful write.
 *
 * **The bug this fixes.** `articles` enables `versions.drafts`. Payload's
 * admin list view therefore queries with `draft: true`, which reads the
 * VERSIONS table (`_articles_v`) and returns the row flagged `latest` for
 * each parent — not `public.articles`. The import wrote every city's archive
 * straight into `public.articles` and never created a version row for any of
 * it, so on a freshly imported database:
 *
 *     payload.find({ collection: 'articles' })              -> 4429
 *     payload.find({ collection: 'articles', draft: true }) ->    0
 *
 * The admin shows "No Results." on a collection holding the entire editorial
 * archive. Nothing errors, nothing logs; the data is simply invisible to the
 * only people who need to edit it. The handful that DO appear are the ones
 * somebody had opened and saved in the admin, which is what created their
 * version rows.
 *
 * `places` is unaffected and shows why: it declares `versions` WITHOUT
 * `drafts`, so its list reads the main table.
 *
 * **Why `db.createVersion` and not `payload.update`.** An update would give
 * the right result and two wrong side effects: `enforcePublishRole` would run
 * against whatever user the script pretends to be, and `publishArticleEvent`
 * would emit one domain event per article — nine thousand spurious "article
 * published" events onto the worker's stream, for articles that were
 * published months ago. `db.createVersion` writes through the same field
 * mapping Payload itself uses (so blocks, arrays and relationships land in
 * the right shape) while bypassing collection hooks entirely.
 *
 * Idempotent: a parent that already has a version row is skipped, so a
 * re-run after a partial failure costs only the read.
 */

import config from '../payload.config.ts'
import { getPayload } from 'payload'

const APPLY = process.env.BACKFILL_APPLY === '1'
const MAX = process.env.BACKFILL_LIMIT ? Number(process.env.BACKFILL_LIMIT) : Infinity
const PAGE_SIZE = 100

if (Number.isNaN(MAX) || MAX <= 0) {
  console.error('[backfill] BACKFILL_LIMIT must be a positive integer')
  process.exit(1)
}

const payload = await getPayload({ config })
const db = payload.db

const city = /\/([^/?]+)(\?|$)/.exec(process.env.DATABASE_URI ?? '')?.[1]
console.log(`[backfill] db="${city}" mode=${APPLY ? 'APPLY' : 'dry-run'}${MAX === Infinity ? '' : ` limit=${MAX}`}`)

let page = 1
let seen = 0
let created = 0
let skipped = 0
let failed = 0

for (;;) {
  const batch = await payload.find({
    collection: 'articles',
    depth: 0, // relationships stay as ids — the shape a version row stores
    limit: PAGE_SIZE,
    overrideAccess: true,
    page,
    pagination: true,
    sort: 'id',
  })

  if (batch.docs.length === 0) break

  for (const doc of batch.docs) {
    if (seen >= MAX) break
    seen++

    // Already has a version? Leave it alone — it may carry a genuine draft
    // that this script has no business overwriting.
    const existing = await payload.db.findVersions({
      collection: 'articles',
      limit: 1,
      pagination: false,
      where: { parent: { equals: doc.id } },
    })
    if (existing.docs.length > 0) {
      skipped++
      continue
    }

    if (!APPLY) {
      created++
      continue
    }

    try {
      const { id, createdAt, updatedAt } = doc
      await db.createVersion({
        autosave: false,
        collectionSlug: 'articles',
        createdAt,
        parent: id,
        returning: false,
        snapshot: false,
        updatedAt,
        // The whole document, timestamps INCLUDED. A version row carries two
        // pairs of them: its own `created_at`/`updated_at` (the arguments
        // above) and the snapshot's `version_created_at`/`version_updated_at`
        // inside `version`. Destructuring the timestamps out of the payload
        // left the second pair NULL on every row — the list view reads the
        // snapshot, so every article showed a blank Last Modified while the
        // version row beside it held the right value.
        versionData: { ...doc, id: undefined, _status: doc._status ?? 'published' },
      })
      created++
    } catch (error) {
      failed++
      // Keep going: one malformed document should not strand the other 9,000.
      console.error(`[backfill] article ${doc.id} failed — ${error?.message ?? error}`)
    }
  }

  if (seen >= MAX || !batch.hasNextPage) break
  page++
}

console.log(
  `[backfill] seen=${seen} ${APPLY ? 'created' : 'would create'}=${created} ` +
    `skipped(existing)=${skipped} failed=${failed}`,
)
if (!APPLY) console.log('[backfill] dry run — nothing written. Re-run with BACKFILL_APPLY=1.')

process.exit(failed > 0 ? 1 : 0)
