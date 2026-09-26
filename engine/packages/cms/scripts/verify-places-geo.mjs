/**
 * Proves the Places editing surface — geo (lat/lng → geography trigger),
 * hours, price band and amenities — works end-to-end through Payload's
 * own API, not just via raw SQL.
 *
 * Run with: npx payload run scripts/verify-places-geo.mjs
 */
import assert from 'node:assert/strict'

import config from '../payload.config.ts'
import { getPayload } from 'payload'

const payload = await getPayload({ config })

const place = await payload.create({
  collection: 'places',
  data: {
    name: 'Verification Beach Club',
    slug: 'verification-beach-club',
    lat: -8.6905,
    lng: 115.1729, // Canggu-ish
    type: 'drink',
    subtype: 'beach-club',
    priceBand: 'upscale',
    amenities: ['pool', 'ocean-view', 'wifi'],
    // Required since ITINERARY-AND-READER-PRODUCTS-PLAN.md §9.2 (Phase 0):
    // `source` records who created the row, and this script's row is
    // created exactly the way an editor manually entering a test place
    // would be.
    source: 'editor',
    hours: [
      { day: 'mon', opens: '10:00', closes: '23:00' },
      { day: 'fri', opens: '10:00', closes: '01:00' },
    ],
    status: 'active',
  },
})

console.log(`[verify] place created id=${place.id}, lat=${place.lat}, lng=${place.lng}`)
console.log(`[verify] amenities=${JSON.stringify(place.amenities)}`)
console.log(`[verify] hours=${JSON.stringify(place.hours)}`)

assert.deepEqual([...place.amenities].sort(), ['ocean-view', 'pool', 'wifi'], 'amenities did not round-trip')
assert.equal(place.hours.length, 2, 'hours did not round-trip')
assert.equal(place.priceBand, 'upscale')

// Confirm the geography column (populated by the trigger in
// 20260908_140000_places_geography.ts) is queryable via raw SQL through
// the SAME connection pool Payload itself uses — proving this isn't a
// side effect only visible outside Payload.
const db = payload.db
const result = await db.pool.query(
  `SELECT ST_AsText(geo::geometry) AS geo_wkt, ST_DWithin(geo, ST_SetSRID(ST_MakePoint($1,$2),4326)::geography, 1000) AS within_1km
     FROM places WHERE id = $3`,
  [115.1729, -8.6905, place.id],
)
console.log(`[verify] geo column: ${JSON.stringify(result.rows[0])}`)
assert.equal(result.rows[0].within_1km, true, 'ST_DWithin against the trigger-populated geo column failed')

await payload.delete({ collection: 'places', id: place.id })
console.log('[verify] places geo/hours/price/amenities OK')
process.exit(0)
