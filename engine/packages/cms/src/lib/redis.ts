/**
 * Domain-event publisher (ARCHITECTURE.md "Publish hook").
 *
 * Payload must not compute anything itself — it only announces. This module
 * is a thin `ioredis` publish wrapper used by `afterChange` hooks to emit
 * events like `article.published` on a Redis pub/sub channel so
 * `engine-worker` can re-embed and re-tag. No queue semantics are assumed
 * beyond what Redis pub/sub gives; if a durable queue (list/stream) is
 * preferred over pub/sub, that is an `engine-worker`-side decision — this
 * module publishes to both a pub/sub channel *and* a Stream so the worker
 * team can pick either without a change here (see `publishDomainEvent`).
 */

import Redis from 'ioredis'

let client: Redis | null = null

function getClient(): Redis | null {
  const url = process.env.REDIS_URL
  if (!url) {
    console.error('[cms] REDIS_URL is not set — domain events will not be emitted')
    return null
  }
  if (!client) {
    client = new Redis(url, {
      lazyConnect: true,
      maxRetriesPerRequest: 2,
      // Boot-time and admin-save UX must never hang on a slow/absent Redis.
      connectTimeout: 3000,
    })
    client.on('error', (err) => {
      console.error(`[cms] redis error: ${err.message}`)
    })
  }
  return client
}

export type DomainEvent = {
  event: string
  site_slug: string
  entity_type: 'article' | 'place' | 'event'
  entity_id: string | number
  occurred_at: string
  payload: Record<string, unknown>
}

const CHANNEL = 'now:domain-events'
const STREAM = 'now:domain-events:stream'

/**
 * Announce a domain event. Never throws — a Redis outage must not block an
 * editor's save. Returns true if the publish succeeded.
 */
export async function publishDomainEvent(event: DomainEvent): Promise<boolean> {
  const redis = getClient()
  if (!redis) return false

  const message = JSON.stringify(event)

  try {
    if (redis.status === 'wait') {
      await redis.connect()
    }
    await Promise.all([
      redis.publish(CHANNEL, message),
      redis.xadd(STREAM, '*', 'event', message),
    ])
    console.log(`[cms] published ${event.event} for ${event.entity_type}:${event.entity_id}`)
    return true
  } catch (err) {
    console.error(
      `[cms] failed to publish domain event ${event.event}: ${
        err instanceof Error ? err.message : String(err)
      }`,
    )
    return false
  }
}

export async function closeRedis(): Promise<void> {
  if (client) {
    await client.quit().catch(() => {})
    client = null
  }
}
