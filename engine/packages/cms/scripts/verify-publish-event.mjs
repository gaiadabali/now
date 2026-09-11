/**
 * Proves the `afterChange` publish hook emits a real message to Redis
 * (localhost:16379) when an article transitions to published — not a
 * simulated/mocked call.
 *
 * Subscribes to the actual channel/stream BEFORE publishing an article via
 * Payload's local API (going through the exact same `afterChange` hook the
 * admin UI and REST API use), then prints whatever Redis delivers.
 *
 * Run with: npx payload run scripts/verify-publish-event.mjs
 */
import config from '../payload.config.ts'
import Redis from 'ioredis'
import { getPayload } from 'payload'

const sub = new Redis(process.env.REDIS_URL)
const received = []
await sub.subscribe('now:domain-events')
sub.on('message', (channel, message) => {
  received.push({ channel, message })
  console.log(`[verify] REDIS MESSAGE on "${channel}": ${message}`)
})

const payload = await getPayload({ config })

console.log('[verify] creating + publishing an article via Payload local API...')
const created = await payload.create({
  collection: 'articles',
  data: {
    title: 'publish-event verification',
    kind: 'article',
    primaryType: 'editorial',
    format: 'news',
    _status: 'published',
  },
  // src/hooks/enforcePublishRole.ts requires editor/admin to move a doc to
  // "published" — this simulates an authenticated editor so the hook (which
  // runs regardless of overrideAccess) allows the transition, the same way
  // an admin-UI request would carry req.user from the session.
  user: { id: 'verify-script', role: 'editor' },
})
console.log(`[verify] article ${created.id} created with _status=${created._status}`)

// Give the pub/sub message a moment to arrive (publish + subscriber
// delivery is asynchronous over the Redis connection).
await new Promise((resolve) => setTimeout(resolve, 500))

// Also confirm the durable Stream entry (see src/lib/redis.ts) via a plain
// client, independent of the pub/sub subscription above.
const plain = new Redis(process.env.REDIS_URL)
const streamEntries = await plain.xrevrange('now:domain-events:stream', '+', '-', 'COUNT', 1)
console.log(`[verify] latest Stream entry (now:domain-events:stream): ${JSON.stringify(streamEntries)}`)

await payload.delete({ collection: 'articles', id: created.id })

if (received.length === 0) {
  console.error('[verify] FAILED — no pub/sub message received on now:domain-events')
  process.exit(1)
}

const parsed = JSON.parse(received[0].message)
if (parsed.event !== 'article.published' || String(parsed.entity_id) !== String(created.id)) {
  console.error(`[verify] FAILED — unexpected event payload: ${JSON.stringify(parsed)}`)
  process.exit(1)
}

console.log('[verify] OK — real article.published message received over Redis pub/sub AND persisted to the Stream')
await sub.quit()
await plain.quit()
process.exit(0)
