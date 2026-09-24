import type { Metadata } from 'next'
import Link from 'next/link'

import { getSiteConfig } from '@/lib/site'
import { decodeEntities, stripTags } from '@/lib/html'

/**
 * Search — the reader-facing surface for the engine's hybrid retrieval.
 *
 * `docs/ui-data-layer.md` draws the line here and it is not negotiable:
 * articles come from the Local API, but **ranking comes from engine-api**.
 * The site must never reimplement it. So this page posts the query straight
 * to `/v1/{site}/search` (BM25 + pgvector, RRF-fused, §7) and renders what
 * comes back, in the order it comes back.
 *
 * It does not re-sort. §10's presentation-bias warning cuts both ways: a
 * surface that quietly reorders the engine's output trains the eventual
 * ranker on a lie.
 */

export const metadata: Metadata = {
  title: 'Search',
  description: 'Search everything we have published.',
}

type SearchHit = {
  entity_id: number
  position: number
  title: string | null
  dek: string | null
  legacy_permalink: string | null
}

async function runSearch(
  site: string,
  q: string,
  facets: string | undefined,
): Promise<{ hits: SearchHit[]; total: number; error?: string }> {
  const base = process.env.ENGINE_API_URL
  if (!base) return { hits: [], total: 0, error: 'Search is not configured.' }

  const url = new URL(`${base}/v1/${site}/search`)
  url.searchParams.set('q', q)
  url.searchParams.set('k', '20')
  if (facets) url.searchParams.append('facets', facets)

  try {
    // No caching: a search result is per-query and personalised later (E7).
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) return { hits: [], total: 0, error: 'Search is temporarily unavailable.' }
    const data = await res.json()
    return { hits: data.hits ?? [], total: data.candidate_count ?? 0 }
  } catch {
    return { hits: [], total: 0, error: 'Search is temporarily unavailable.' }
  }
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}) {
  const site = await getSiteConfig()
  const params = (await searchParams) ?? {}
  const q = typeof params.q === 'string' ? params.q.trim() : ''
  const facets = typeof params.facets === 'string' ? params.facets : undefined

  const { hits, total, error } = q || facets ? await runSearch(site.slug, q || '*', facets) : { hits: [], total: 0 }

  return (
    <div className="shell">
      <header className="band">
        <p className="kicker kicker--red">Search</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          {q ? q : 'Search'}
        </h1>

        {/* A plain GET form: the query belongs in the URL so a search is
            shareable, and this page stays a server component. */}
        <form
          action="/search"
          method="get"
          style={{ marginTop: 'var(--space-l)', display: 'flex', gap: 'var(--space-s)', maxWidth: '40rem' }}
        >
          <input
            name="q"
            type="search"
            defaultValue={q}
            placeholder="Restaurants, hotels, neighbourhoods…"
            aria-label="Search"
            style={{ flex: 1, padding: 'var(--space-s)', font: 'inherit', border: '1px solid currentColor' }}
          />
          <button
            type="submit"
            className="kicker kicker--red"
            style={{ padding: 'var(--space-s) var(--space-m)', border: '1px solid currentColor', background: 'transparent' }}
          >
            Search →
          </button>
        </form>
      </header>

      <section className="band" data-reveal>
        {error ? (
          <p className="dek">{error}</p>
        ) : !q && !facets ? (
          <p className="dek">Type anything — a dish, a district, a hotel name.</p>
        ) : hits.length === 0 ? (
          <p className="dek">Nothing matched. Try fewer words.</p>
        ) : (
          <>
            <p className="dek" style={{ marginBottom: 'var(--space-l)' }}>
              {hits.length} of {total} searched.
            </p>
            {/* Ruled rows rather than a bare grid of gaps — the index
                treatment DESIGN-SYSTEM §2 already uses for Latest, applied
                here because a result list is exactly that: a dense list
                with no thumbnail to carry hierarchy on its own, which is
                why the headline takes the same `display--medium` weight a
                card headline does rather than the plain system-font `<h2>`
                this used to be. */}
            <div className="search-results">
              {hits.map((hit) => {
                const slug = (hit.legacy_permalink ?? '').replace(/^\/+|\/+$/g, '')
                return (
                  <article key={hit.entity_id}>
                    <h2 className="display display--medium" style={{ fontSize: 'var(--t-title)', marginBottom: 'var(--space-2xs)' }}>
                      {/*
                        Decoded here as well as in the Payload mapper: these
                        hits come from engine-api, not the Local API, so they
                        bypass `toArticle` entirely. 81 Bali titles store
                        entities, and a result reading "Catch &amp; Grill" is
                        the same bug on a different surface.
                      */}
                      {slug ? (
                        <Link href={`/${slug}`}>{decodeEntities(hit.title ?? '')}</Link>
                      ) : (
                        decodeEntities(hit.title ?? '')
                      )}
                    </h2>
                    {hit.dek ? <p className="dek">{stripTags(hit.dek)}</p> : null}
                  </article>
                )
              })}
            </div>
          </>
        )}
      </section>
    </div>
  )
}
