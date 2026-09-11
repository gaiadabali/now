/**
 * Renders the review queue exactly as the admin list view would query it —
 * confidence ascending, then applies each required filter one at a time —
 * and prints real rows back, since `next dev`/`next build` cannot run from
 * this checkout path (D1) and the admin UI itself cannot be screenshotted.
 *
 * Run with: npx payload run scripts/verify-review-queue-render.mjs
 */
import config from '../payload.config.ts'
import { getPayload } from 'payload'

const payload = await getPayload({ config })

console.log('\n=== Default query (no explicit sort) — proves defaultSort: "confidence" ===')
const defaultOrder = await payload.find({ collection: 'classification-reviews', depth: 0, limit: 20 })
for (const row of defaultOrder.docs) {
  console.log(
    `  #${row.id} confidence=${row.confidence} band=${row.confidenceBand} facet=${row.facetKey} ` +
      `state=${row.reviewState} entity=${row.entityType}:${row.entity}`,
  )
}
const confidences = defaultOrder.docs.map((d) => d.confidence)
const isAscending = confidences.every((c, i) => i === 0 || c >= confidences[i - 1])
console.log(`[verify] ascending by confidence: ${isAscending}`)

console.log('\n=== Filter: reviewState=pending ===')
const pendingOnly = await payload.find({ collection: 'classification-reviews', where: { reviewState: { equals: 'pending' } }, depth: 0 })
console.log(`  ${pendingOnly.totalDocs} row(s): ${pendingOnly.docs.map((d) => d.id).join(', ')}`)

console.log('\n=== Filter: facetKey=type ===')
const typeOnly = await payload.find({ collection: 'classification-reviews', where: { facetKey: { equals: 'type' } }, depth: 0 })
console.log(`  ${typeOnly.totalDocs} row(s): ${typeOnly.docs.map((d) => d.id).join(', ')}`)

console.log('\n=== Filter: confidenceBand=low ===')
const lowBand = await payload.find({ collection: 'classification-reviews', where: { confidenceBand: { equals: 'low' } }, depth: 0 })
console.log(`  ${lowBand.totalDocs} row(s): ${lowBand.docs.map((d) => d.id).join(', ')}`)

console.log('\n=== Filter: siteSlug (the "city" filter) ===')
const bySite = await payload.find({ collection: 'classification-reviews', where: { siteSlug: { equals: process.env.SITE_SLUG ?? 'unknown' } }, depth: 0 })
console.log(`  ${bySite.totalDocs} row(s) for siteSlug="${process.env.SITE_SLUG}"`)

console.log('\n=== Evidence view for one row (article title + legacy category + reasoning) ===')
const withEntity = await payload.find({ collection: 'classification-reviews', where: { entityType: { equals: 'article' } }, depth: 1, limit: 1 })
const sample = withEntity.docs[0]
if (sample) {
  console.log(`  review #${sample.id}`)
  console.log(`  entity title: "${sample.entity?.value?.title ?? sample.entity?.title}"`)
  console.log(`  legacy category: "${sample.legacyCategory}"`)
  console.log(`  proposed: ${sample.facetKey}=${sample.proposedValue} (confidence ${sample.confidence}, band ${sample.confidenceBand})`)
  console.log(`  reasoning: "${sample.reasoning}"`)
}

console.log('\n=== Throughput endpoint (items/hour) ===')
const res = await fetch(`http://localhost:${process.env.PORT ?? 3000}/api/classification-reviews/throughput?hours=24`).catch(() => null)
if (res && res.ok) {
  console.log(`  HTTP: ${JSON.stringify(await res.json())}`)
} else {
  console.log('  (no HTTP server running in this local-API script context — computing the same query directly instead)')
  const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
  const reviewed = await payload.find({
    collection: 'classification-reviews',
    where: { and: [{ reviewState: { not_equals: 'pending' } }, { reviewedAt: { greater_than_equal: since } }] },
    limit: 0,
    depth: 0,
  })
  console.log(`  reviewedCount=${reviewed.totalDocs} windowHours=24 itemsPerHour=${Math.round((reviewed.totalDocs / 24) * 100) / 100}`)
}

process.exit(0)
