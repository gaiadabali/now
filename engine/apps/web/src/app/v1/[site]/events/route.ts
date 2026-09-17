import { getSiteConfig } from '@/lib/site'

/**
 * `POST /v1/{site}/events` on the reader origin — the beacon's endpoint.
 *
 * ## Why this exists at all
 *
 * The beacon derives its endpoint from its own `<script src>` origin
 * (`packages/beacon/README.md`, "Transport"), so it posts to the site it is
 * loaded from: `https://www.{city}/v1/{city}/events`. Nothing served that
 * path. The in-repo edge config routes `/v1` only on the API's own hostname
 * (`engine/infra/caddy/Caddyfile`), and in the deployment that actually runs
 * (`deploy/docker-compose.yml`) `engine-api` is published on `127.0.0.1` with
 * no public hostname at all. So every batch the beacon has ever sent hit the
 * Next app and 404'd, which is a large part of why both tables are empty.
 *
 * Rejected: a `rewrites()` entry in `next.config.mjs`. Rewrites are resolved
 * at BUILD time into the routes manifest, and `ENGINE_API_URL` is not set
 * during `docker build` — the destination would bake in empty. This project's
 * whole §3.5 premise is one image configured by runtime env, and a route
 * handler reads `process.env` per request, exactly as `(site)/search/page.tsx`
 * already does for the same variable.
 *
 * Rejected: pointing the beacon at the API directly with
 * `NEXT_PUBLIC_BEACON_ENDPOINT`. That needs the API published on a public
 * hostname (it is not), and it turns every batch into a cross-origin request
 * whose only gate is the CORS allowlist. Same-origin has no preflight, no
 * allowlist to drift, and nothing about the API's address in client HTML.
 *
 * The path shape is the API's own, unchanged, so a deployment that later
 * fronts `/v1` at the edge can delete this file and the beacon will not
 * notice.
 *
 * ## Tenancy
 *
 * This process serves exactly one city (`src/lib/site.ts`). The `{site}`
 * segment is therefore checked against it and a mismatch is a 404 — a page on
 * one city's origin cannot write behaviour into another city's database, even
 * though one API instance can reach both. The segment stays in the path only
 * because it is the beacon's contract, not because this route would honour
 * any value in it.
 */
export const dynamic = 'force-dynamic'

export async function POST(
  request: Request,
  { params }: { params: Promise<{ site: string }> },
): Promise<Response> {
  const base = process.env.ENGINE_API_URL
  if (!base) {
    // Loud, because the failure it replaces was silent: a missing API URL
    // means behaviour is being collected in the browser and thrown away.
    console.error('[beacon] ENGINE_API_URL is not set — dropping an events batch.')
    return new Response(null, { status: 503 })
  }

  const { site } = await params
  const config = await getSiteConfig()
  if (site !== config.slug) return new Response(null, { status: 404 })

  // Forwarded verbatim. Validation, rate limiting and the batch-size ceiling
  // all live in the API (`app/api/v1/events.py`); re-implementing any of it
  // here would be a second, drifting copy of a contract this app does not own.
  const body = await request.text()

  const headers: Record<string, string> = {
    'content-type': request.headers.get('content-type') ?? 'application/json',
  }
  // The API checks `Origin` against the site registry's hostname. Passing the
  // browser's through keeps that check meaningful instead of showing the API
  // this server's own request.
  const origin = request.headers.get('origin')
  if (origin) headers.origin = origin

  let upstream: Response
  try {
    upstream = await fetch(`${base}/v1/${encodeURIComponent(site)}/events`, {
      method: 'POST',
      headers,
      body,
      cache: 'no-store',
    })
  } catch (error) {
    console.error('[beacon] events upstream unreachable:', error)
    return new Response(null, { status: 502 })
  }

  // 204 is the success case and must stay bodyless. Everything else is passed
  // back as-is so a payload the API rejects is visible in devtools rather than
  // being flattened into a generic error here.
  if (upstream.status === 204) return new Response(null, { status: 204 })
  const text = await upstream.text()
  return new Response(text, {
    status: upstream.status,
    headers: { 'content-type': upstream.headers.get('content-type') ?? 'text/plain' },
  })
}
