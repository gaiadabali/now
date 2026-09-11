/**
 * Headless boot verification — no Next.js dev server required. Proves the
 * Payload config connects to whatever `DATABASE_URI` points at, and reports
 * which database it landed on. Run with:
 *
 *   npx payload run scripts/boot-check.mjs
 *
 * with DATABASE_URI / SITE_SLUG set to the target city.
 */
import config from '../payload.config.ts'
import { getPayload } from 'payload'

const payload = await getPayload({ config })

const dbNameMatch = /\/([^/?]+)(\?|$)/.exec(process.env.DATABASE_URI ?? '')
console.log(`[boot-check] SITE_SLUG=${process.env.SITE_SLUG} DATABASE_URI targets db="${dbNameMatch?.[1]}"`)

const articles = await payload.find({ collection: 'articles', limit: 1 })
const places = await payload.find({ collection: 'places', limit: 1 })
console.log(`[boot-check] articles collection reachable — ${articles.totalDocs} doc(s)`)
console.log(`[boot-check] places collection reachable — ${places.totalDocs} doc(s)`)
console.log('[boot-check] OK')

process.exit(0)
