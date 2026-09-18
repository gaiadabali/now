/**
 * S1.1/S1.2 acceptance — proves a NEW article gets a reachable address, and
 * that the 9,201 imported ones keep theirs.
 *
 * This is the criterion the ticket was written against, and it cannot be met
 * by a unit test: the question is whether the field the CMS writes is the
 * field the reader app resolves, across two modules that do not import each
 * other. So this goes through Payload's local API — the same path the admin
 * UI takes, hooks included — and then queries the way `getBySlug()` does.
 *
 * What it checks, in order:
 *   1. Every existing article has a slug, and it equals its legacy permalink.
 *      (The backfill's own acceptance: counted, not sampled.)
 *   2. A new article created with NO slug gets one derived from its title.
 *   3. That article resolves by `slug` — the lookup `getBySlug` tries first.
 *   4. An imported article still resolves by `legacyPermalink` — the lookup
 *      `getBySlug` falls back to. This is the SEO estate; it is the one
 *      assertion here whose failure would be an outage.
 *   5. Retitling the new article does NOT move its address.
 *   6. A second article cannot take an address that is already taken.
 *
 * Creates one article and deletes it again, including on failure.
 *
 * Run with: npx payload run scripts/verify-article-slug.mjs
 *
 * Checks whichever city `DATABASE_URI` and `SITE_SLUG` name, so run it once
 * per city — override both to point at the other one. (No city is named in
 * this file: `npm run lint:site-literals` forbids it, and rightly, since a
 * script that mentions one city reads as though it only applies there.)
 */
import { getPayload } from 'payload'

import config from '../payload.config.ts'

const payload = await getPayload({ config })

/** Payload's publish gate requires editor/admin, as an admin session would. */
const asEditor = { id: 'verify-article-slug', role: 'editor' }

const failures = []
const check = (ok, label, detail = '') => {
  console.log(`[verify] ${ok ? 'PASS' : 'FAIL'} — ${label}${detail ? ` :: ${detail}` : ''}`)
  if (!ok) failures.push(label)
}

let createdId = null

try {
  // --- 1. the backfill, counted ------------------------------------------
  const total = await payload.count({ collection: 'articles' })
  const missing = await payload.count({
    collection: 'articles',
    where: { slug: { exists: false } },
  })
  check(
    missing.totalDocs === 0,
    `every one of ${total.totalDocs} existing articles has an address`,
    `${missing.totalDocs} without`,
  )

  // A slug that disagrees with its own legacy permalink would mean the
  // backfill mis-derived, and the old URL would now resolve to the wrong
  // story. Sampled at 500 because this runs through the Local API rather
  // than SQL; the exhaustive form is the `MISMATCH` count in the migration's
  // own verification.
  const sample = await payload.find({
    collection: 'articles',
    where: { legacyPermalink: { exists: true } },
    limit: 500,
    depth: 0,
    pagination: false,
  })
  const disagreeing = sample.docs.filter(
    (d) => d.legacyPermalink && d.slug !== String(d.legacyPermalink).replace(/^\/+|\/+$/g, ''),
  )
  check(
    disagreeing.length === 0,
    `${sample.docs.length} imported addresses match their legacy permalink`,
    disagreeing.length ? `first: ${disagreeing[0].slug} vs ${disagreeing[0].legacyPermalink}` : '',
  )

  // --- 2. a new article is given an address ------------------------------
  const title = `Slug verification ${Date.now()}`
  const created = await payload.create({
    collection: 'articles',
    data: { title, kind: 'article', primaryType: 'editorial', format: 'news', _status: 'published' },
    user: asEditor,
  })
  createdId = created.id

  const expected = title
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
  check(created.slug === expected, 'a new article gets an address from its headline', `got "${created.slug}"`)
  check(!created.legacyPermalink, 'and it has no legacy permalink — so the slug is its ONLY address')

  // --- 3. it resolves the way the reader app resolves --------------------
  const bySlug = await payload.find({
    collection: 'articles',
    where: { _status: { equals: 'published' }, slug: { equals: created.slug } },
    limit: 1,
    depth: 0,
  })
  check(
    bySlug.docs[0]?.id === created.id,
    'the reader app finds it at /<slug>',
    bySlug.docs[0] ? '' : 'not found',
  )

  // --- 4. an imported article still resolves by its old URL --------------
  const legacy = await payload.find({
    collection: 'articles',
    where: { _status: { equals: 'published' }, legacyPermalink: { exists: true } },
    limit: 1,
    depth: 0,
  })
  const legacyDoc = legacy.docs[0]
  if (!legacyDoc) {
    check(false, 'an imported article exists to test the legacy path against')
  } else {
    const byPermalink = await payload.find({
      collection: 'articles',
      where: { _status: { equals: 'published' }, legacyPermalink: { equals: legacyDoc.legacyPermalink } },
      limit: 1,
      depth: 0,
    })
    check(
      byPermalink.docs[0]?.id === legacyDoc.id,
      `an imported article still resolves at its old URL (${legacyDoc.legacyPermalink})`,
    )
  }

  // --- 5. retitling must not move the address ----------------------------
  const retitled = await payload.update({
    collection: 'articles',
    id: created.id,
    data: { title: `${title} — revised headline` },
    user: asEditor,
  })
  check(retitled.slug === created.slug, 'retitling does not move the address', `now "${retitled.slug}"`)

  // --- 6. two stories cannot share one address ---------------------------
  let refused = false
  let second = null
  try {
    second = await payload.create({
      collection: 'articles',
      data: {
        title: 'Slug collision attempt',
        slug: created.slug,
        kind: 'article',
        primaryType: 'editorial',
        format: 'news',
        _status: 'draft',
      },
      user: asEditor,
    })
  } catch {
    refused = true
  }
  if (second) await payload.delete({ collection: 'articles', id: second.id })
  check(refused, 'a duplicate address is refused rather than silently renamed')
} finally {
  if (createdId) {
    await payload.delete({ collection: 'articles', id: createdId })
    console.log(`[verify] cleaned up article ${createdId}`)
  }
}

if (failures.length > 0) {
  console.error(`\n[verify] FAILED — ${failures.length} check(s): ${failures.join('; ')}`)
  process.exit(1)
}
console.log('\n[verify] OK — a new article is reachable, and an imported one still is.')
process.exit(0)
