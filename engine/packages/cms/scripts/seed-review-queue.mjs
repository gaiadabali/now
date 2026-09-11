/**
 * SYNTHETIC seed for the E2.8 review queue.
 *
 * E2.1 (the classifier) has not run — `select count(*) from
 * engine.entity_terms` is 0 in every city DB as of this ticket, and every
 * real article in the first-loaded city DB has `primary_type IS NULL`
 * (PROGRESS.md F50/F74). There is therefore no real low-confidence
 * classification to point this queue at yet. Everything this script writes
 * is FABRICATED evidence over REAL, existing articles/places (picked up
 * live from whatever DATABASE_URI points at) — good enough to prove the
 * queue's UI/filtering/sorting/workflow works, not a claim about what the
 * real classifier will actually say. Re-run freely; it is not idempotent
 * (each run adds another batch) — delete via the admin UI or
 * `payload.delete` if you want a clean slate.
 *
 * Run with: npx payload run scripts/seed-review-queue.mjs
 */
import config from '../payload.config.ts'
import { getPayload } from 'payload'

const payload = await getPayload({ config })

// `reviewedBy` is a real `relationship: 'users'` field (not a free-typed
// string) — it must point at an actual users.id, so the acting "editor"
// for this seed run needs to be a real row, not just a fake { id, role }
// object like the RBAC verify scripts use for access-control checks only.
const existingEditor = await payload.find({ collection: 'users', where: { role: { equals: 'editor' } }, limit: 1 })
const editorUser =
  existingEditor.docs[0] ??
  (await payload.create({
    collection: 'users',
    data: { email: 'e2.8-seed-editor@example.invalid', password: 'seed-only-not-a-real-login-1!', role: 'editor', name: 'E2.8 seed script' },
  }))
console.log(`[seed] acting as editor user ${editorUser.id} (${editorUser.email})`)

const articles = await payload.find({ collection: 'articles', limit: 2, sort: 'id' })
const places = await payload.find({ collection: 'places', limit: 1, sort: 'id' })

if (articles.docs.length < 2 || places.docs.length < 1) {
  console.error('[seed] need at least 2 articles and 1 place already loaded — run E1.8 first.')
  process.exit(1)
}

const [articleA, articleB] = articles.docs
const [placeA] = places.docs

// Rows that stay `pending`: attached to REAL, EXISTING articles/places, safe
// because a pending review never triggers the write-back hook — nothing
// about these rows is mutated. Good for showing the "evidence" view against
// real content without touching it.
const pendingRows = [
  {
    entity: { relationTo: 'articles', value: articleA.id },
    legacyCategory: 'Uncategorized',
    facetKey: 'type',
    proposedValue: 'editorial',
    confidence: 0.31,
    reasoning:
      'SYNTHETIC — title and first paragraph read as a generic listicle intro; no venue names, ' +
      'prices, or event dates detected. Weak signal either way, defaulting to "editorial".',
  },
  {
    entity: { relationTo: 'articles', value: articleB.id },
    legacyCategory: 'Food & Drink',
    facetKey: 'format',
    proposedValue: 'feature',
    confidence: 0.44,
    reasoning:
      'SYNTHETIC — numbered heading pattern ("1. ...", "2. ...") detected 6 times, but the article ' +
      'also contains a long narrative intro atypical for a pure listicle — mixed signal.',
  },
  {
    entity: { relationTo: 'places', value: placeA.id },
    legacyCategory: 'Hotels & Resorts',
    facetKey: 'subtype',
    proposedValue: 'boutique-hotel',
    confidence: 0.58,
    reasoning:
      'SYNTHETIC — "boutique" appears once in body copy; room count and amenities list are closer ' +
      'to a mid-size resort than the boutique-hotel term\'s usual profile.',
  },
]

const created = []
for (const evidence of pendingRows) {
  const doc = await payload.create({
    collection: 'classification-reviews',
    data: { ...evidence, weight: 1, source: 'ai', reviewState: 'pending' },
  })
  created.push(doc)
  console.log(
    `[seed] pending review ${doc.id} — ${doc.entityType} ${JSON.stringify(doc.entity)} ` +
      `facet=${doc.facetKey} confidence=${doc.confidence} band=${doc.confidenceBand}`,
  )
}

// Rows that are ALREADY decided (accepted / unclassifiable): these DO
// trigger the write-back hook, so they run against fresh, disposable
// fixtures this script creates itself — never against the 4,772/177 real
// rows above — so this seed never leaves a mutated real entity behind.
const fixtureArticle = await payload.create({
  collection: 'articles',
  data: { title: '[E2.8 seed fixture] nightlife feature', kind: 'article', primaryType: 'drink', format: 'news' },
})
const fixturePlace = await payload.create({
  collection: 'places',
  data: {
    name: '[E2.8 seed fixture] unnamed venue',
    slug: `e28-seed-fixture-${Date.now()}`,
    type: 'editorial',
    subtype: 'city-guide',
  },
})

const acceptedReview = await payload.create({
  collection: 'classification-reviews',
  data: {
    entity: { relationTo: 'articles', value: fixtureArticle.id },
    legacyCategory: 'Nightlife',
    facetKey: 'type',
    proposedValue: 'drink',
    confidence: 0.79,
    reasoning:
      'SYNTHETIC — strong bar/cocktail vocabulary throughout, one paragraph also reviews the food ' +
      'menu at length — plausibly "eat" instead. Below the 0.85 auto-apply bar either way.',
    weight: 1,
    source: 'ai',
    reviewState: 'pending',
  },
})
const acceptedDecided = await payload.update({
  collection: 'classification-reviews',
  id: acceptedReview.id,
  data: { reviewState: 'accepted' },
  user: { id: editorUser.id, role: 'editor' },
})
console.log(
  `[seed] accepted review ${acceptedDecided.id} on fixture article ${fixtureArticle.id} -> ` +
    `finalValue=${acceptedDecided.finalValue}, source=${acceptedDecided.source}`,
)

const unclassifiableReview = await payload.create({
  collection: 'classification-reviews',
  data: {
    entity: { relationTo: 'places', value: fixturePlace.id },
    legacyCategory: 'Uncategorized',
    facetKey: 'type',
    proposedValue: 'stay',
    confidence: 0.18,
    reasoning:
      'SYNTHETIC, illustrating the "Order Form" problem this ticket describes: extracted body text ' +
      'is almost entirely form fields ("Name:", "Check-in date:", "Signature:") with no descriptive ' +
      'prose at all — not confidently a venue, an article, or an event.',
    weight: 1,
    source: 'ai',
    reviewState: 'pending',
  },
})
const unclassifiableDecided = await payload.update({
  collection: 'classification-reviews',
  id: unclassifiableReview.id,
  data: { reviewState: 'unclassifiable' },
  user: { id: editorUser.id, role: 'editor' },
})
console.log(
  `[seed] unclassifiable review ${unclassifiableDecided.id} on fixture place ${fixturePlace.id} -> ` +
    `finalValue=${unclassifiableDecided.finalValue} (F49 sentinel applied to the fixture place's own type field)`,
)

console.log(
  `[seed] OK — ${created.length + 2} synthetic review rows created (3 pending on real content, 1 accepted ` +
    '+ 1 unclassifiable on disposable fixtures). Open /admin/collections/classification-reviews',
)
console.log('[seed] REMINDER: every value/confidence/reasoning here is fabricated. See this script\'s header comment.')
process.exit(0)
