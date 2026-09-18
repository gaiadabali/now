import Link from 'next/link'

import { requireStaffAdmin } from '@/lib/auth'
import { listRegistrySites } from '@/lib/queries'

import { getFacetCoverage } from './facetCoverage'
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
  const [sites, coverage] = await Promise.all([listRegistrySites(), getFacetCoverage()])

  // Aggregated for the KPI row only — the per-site chips below still show the
  // real per-field verdict `FieldPill` computes; this is the same three
  // predicates summed across every row, not a new source of truth.
  let governedFieldCount = 0
  let totalFieldCount = 0
  for (const site of sites) {
    const nav = navReport(site.nav)
    const brand = brandReport(site.brand_tokens)
    const rails = railsReport(site.home_rails)
    governedFieldCount += [nav.governed, brand.governed, rails.governed].filter(Boolean).length
    totalFieldCount += 3
  }
  const facetsAtZero = coverage.rows.filter((row) => row.assignments === 0)
  const maxAssignments = Math.max(1, ...coverage.rows.map((row) => row.assignments))

  return (
    <>
      <h1>Platform — sites</h1>
      <p className="platform__sub">
        What each city&rsquo;s reader masthead, marks and homepage rail order actually come from
        right now. A field reading <strong>falling back to file</strong> is not broken — it is the
        normal state for a row the console has never touched, and the reader still renders
        correctly from the baked config. Open a site to change what wins.
      </p>

      <div className="platform__kpis">
        <div className="platform__kpi">
          <div className="platform__kpi-n">{sites.length}</div>
          <div className="platform__kpi-k">Site{sites.length === 1 ? '' : 's'} registered</div>
        </div>
        <div className="platform__kpi">
          <div className="platform__kpi-n">
            {governedFieldCount} / {totalFieldCount}
          </div>
          <div className="platform__kpi-k">Config fields governed here</div>
        </div>
        <div className="platform__kpi">
          <div className="platform__kpi-n">{coverage.articleCount.toLocaleString()}</div>
          <div className="platform__kpi-k">Classified articles, this city</div>
        </div>
        <div className="platform__kpi">
          <div className={`platform__kpi-n ${facetsAtZero.length > 0 ? 'platform__kpi-n--bad' : ''}`}>
            {facetsAtZero.length}
          </div>
          <div className="platform__kpi-k">
            of {coverage.rows.length} facet{coverage.rows.length === 1 ? '' : 's'} with zero coverage
          </div>
        </div>
      </div>

      <h2>Facet coverage</h2>
      <p className="platform__sub">{coverage.scopeNote}</p>
      <ul className="platform__coverage">
        {coverage.rows.map((row) => (
          <li className="platform__coverage-row" key={row.facetKey}>
            <span className="platform__coverage-key">{row.facetKey}</span>
            <span className="platform__coverage-bar" role="img" aria-label={`${row.assignments.toLocaleString()} assignments`}>
              <span
                className={`platform__coverage-fill ${row.assignments === 0 ? 'platform__coverage-fill--zero' : ''}`}
                style={{ width: row.assignments === 0 ? '100%' : `${Math.max(2, (row.assignments / maxAssignments) * 100)}%` }}
              />
            </span>
            <span className="platform__coverage-n">{row.assignments.toLocaleString()}</span>
          </li>
        ))}
      </ul>

      <h2>Sites</h2>
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
