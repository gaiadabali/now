import Link from 'next/link'

import { requireStaffAdmin } from '@/lib/auth'
import { listRegistrySites } from '@/lib/queries'

import { brandReport, jsonColumnGoverned, navReport, railsReport } from './registry'
import { siteHref } from './paths'

/**
 * `/team-editor/platform` — the sites registry.
 *
 * S5.1 (docs/SURFACES-PLAN.md §S5): the platform console governs `nav`,
 * `brand_tokens`, `home_rails` and `ranking_weights` on `engine.sites`, and
 * until S1.3 nothing read any of them — every row was `{}` and the reader
 * app read a baked config file instead. This index exists to answer one
 * question per site, per field: **is this governed, or is it silently
 * falling back to the file?** That distinction is not visible anywhere else
 * — `psql` shows `{}` and a merged `getSiteConfig()` result looks identical
 * to a real registry value once the fallback has filled it in.
 *
 * Role-gated here, not in a layout. A layout guard is a rendering
 * convenience and not an access control (`lib/auth.ts`); this is platform-
 * wide configuration reachable from any city's admin session
 * (docs/SURFACES-PLAN.md D-S1), so `requireStaffAdmin()` is the first line of
 * this function, before any query — matching `requireCommerceAccess()` in
 * `team-editor/commerce/**`.
 */
export async function RegistryIndexView() {
  await requireStaffAdmin()
  const sites = await listRegistrySites()

  return (
    <>
      <h1>Platform — sites</h1>
      <p className="platform__sub">
        What each city&rsquo;s reader masthead, marks and homepage rail order actually come from
        right now. A field reading <strong>falling back to file</strong> is not broken — it is the
        normal state for a row the console has never touched, and the reader still renders
        correctly from the baked config. Open a site to change what wins.
      </p>

      {sites.length === 0 ? (
        <div className="platform__empty">No sites are registered.</div>
      ) : (
        <table className="platform__table">
          <thead>
            <tr>
              <th>Site</th>
              <th>Hostname</th>
              <th>Status</th>
              <th>Nav</th>
              <th>Brand</th>
              <th>Home rails</th>
              <th>Ranking weights</th>
            </tr>
          </thead>
          <tbody>
            {sites.map((site) => {
              const nav = navReport(site.nav)
              const brand = brandReport(site.brand_tokens)
              const rails = railsReport(site.home_rails)
              const rankingWeights = jsonColumnGoverned(site.ranking_weights)
              return (
                <tr key={site.id}>
                  <td>
                    <Link href={siteHref(site.slug)}>{site.name}</Link>
                    <div className="platform__muted">{site.slug}</div>
                  </td>
                  <td>{site.hostname}</td>
                  <td>{site.status}</td>
                  <td>
                    <FieldPill
                      governed={nav.governed}
                      invalid={!nav.governed && !nav.emptyColumn}
                      count={Array.isArray(site.nav) ? site.nav.length : undefined}
                    />
                  </td>
                  <td>
                    <FieldPill governed={brand.governed} invalid={false} count={Object.keys(brand.fields).length} />
                  </td>
                  <td>
                    <FieldPill
                      governed={rails.governed}
                      invalid={!rails.governed && !rails.emptyColumn}
                      count={Array.isArray(site.home_rails) ? site.home_rails.length : undefined}
                    />
                  </td>
                  <td>
                    <span className="platform__muted" title="No reader consumes this column yet.">
                      {rankingWeights ? 'set' : '—'}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </>
  )
}

/**
 * One pill, one verdict. `invalid` is a console-only nuance on top of the
 * reader's binary governed/fallback: a non-empty value `navFrom`/`railsFrom`
 * still rejects is not the same situation as a row nobody has ever edited,
 * even though a reader falls back in both cases (see `registry.ts`).
 */
function FieldPill({ governed, invalid, count }: { governed: boolean; invalid: boolean; count?: number }) {
  if (governed) {
    return (
      <span className="platform__pill platform__pill--governed" title="A reader uses this value.">
        governed{typeof count === 'number' ? ` · ${count}` : ''}
      </span>
    )
  }
  if (invalid) {
    return (
      <span
        className="platform__pill platform__pill--invalid"
        title="This column holds a value, but its shape is rejected on read — a reader falls back to the config file as if it were empty."
      >
        invalid — falling back
      </span>
    )
  }
  return (
    <span className="platform__pill" title="This column is empty ({} or []). A reader uses the config file.">
      falling back to file
    </span>
  )
}
