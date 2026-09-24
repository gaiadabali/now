import { requireRailAnalyticsAccess } from '@/lib/auth'
import { getCoverage, getExperiments, getRailSummaries, getTrackingHealth } from './analytics'

/**
 * "How suggestions are doing" — `/team-editor/platform/rails`.
 *
 * Read-only, admin/editor (`requireRailAnalyticsAccess`, `lib/auth.ts`).
 * Reached through `PlatformView`'s existing segment dispatcher, the same
 * way `commerce/orgs/[id]/partnerships/**` was added without a new Payload
 * view registration — see that ticket's own notes on why a prefix-matched
 * custom view needs none for a new path under it.
 */

function pct(n: number | null, digits = 1): string {
  if (n === null) return '—'
  return `${(n * 100).toFixed(digits)}%`
}

function plural(n: number, one: string, many: string): string {
  return `${n.toLocaleString()} ${n === 1 ? one : many}`
}

export async function RailsAnalyticsView() {
  await requireRailAnalyticsAccess()
  const citySlug = process.env.SITE_SLUG || 'this city'

  const [summaries, experiments, coverage, health] = await Promise.all([
    getRailSummaries(),
    getExperiments(),
    getCoverage(),
    getTrackingHealth(),
  ])

  const coverageByRail = new Map(coverage.map((c) => [c.rail, c]))
  const totalImpressions30d = summaries.reduce((s, r) => s + r.impressions30d, 0)
  const totalClicks30d = summaries.reduce((s, r) => s + r.clicks30d, 0)
  const railsWithData = summaries.filter((r) => r.hasData).length
  const maxPositionClicks = Math.max(1, ...summaries.flatMap((r) => r.clicksByPosition30d.map((p) => p.clicks)))
  const maxDayEvents = Math.max(1, ...health.days.map((d) => d.events))

  return (
    <>
      <h1>How suggestions are doing</h1>
      <p className="platform__sub">
        Live from {citySlug}&rsquo;s own database — not a two-city total. A process serves exactly
        one city (ARCHITECTURE.md §3.5), the same limit <code>facetCoverage.ts</code> labels on the
        classification-health screen. Sign in to another city&rsquo;s admin for its own numbers.
      </p>

      <div className="platform__kpis">
        <div className="platform__kpi">
          <div className="platform__kpi-n">{railsWithData} / {summaries.length}</div>
          <div className="platform__kpi-k">Rails with any traffic (30d)</div>
        </div>
        <div className="platform__kpi">
          <div className="platform__kpi-n">{totalImpressions30d.toLocaleString()}</div>
          <div className="platform__kpi-k">Impressions, all rails (30d)</div>
        </div>
        <div className="platform__kpi">
          <div className="platform__kpi-n">{totalClicks30d.toLocaleString()}</div>
          <div className="platform__kpi-k">Clicks, all rails (30d)</div>
        </div>
        <div className="platform__kpi">
          <div className={`platform__kpi-n ${health.quiet ? 'platform__kpi-n--bad' : ''}`}>
            {health.daysSinceLastEvent === null ? '—' : health.daysSinceLastEvent}
          </div>
          <div className="platform__kpi-k">Days since the beacon last sent anything</div>
        </div>
      </div>

      <h2>Per rail</h2>
      <p className="platform__sub">
        Every rail this site can show is listed, whether or not it has served anything yet — a rail
        at zero is a real, current fact, not a missing chart.
      </p>

      {summaries.map((rail) => {
        const cov = coverageByRail.get(rail.rail)
        return (
          <div className="ws4-rail-card" key={rail.rail}>
            <div className="ws4-rail-card__head">
              <h3>{rail.rail}</h3>
              {!rail.hasData ? <span className="platform__pill">no traffic yet</span> : null}
            </div>

            {rail.hasData ? (
              <>
                <div className="ws4-rail-card__stats">
                  <div>
                    <span className="ws4-rail-card__label">Last 7 days</span>
                    <span className="ws4-rail-card__value">
                      {rail.impressions7d.toLocaleString()} impressions · {rail.clicks7d.toLocaleString()} clicks · {pct(rail.ctr7d)} CTR
                    </span>
                  </div>
                  <div>
                    <span className="ws4-rail-card__label">Last 30 days</span>
                    <span className="ws4-rail-card__value">
                      {rail.impressions30d.toLocaleString()} impressions · {rail.clicks30d.toLocaleString()} clicks · {pct(rail.ctr30d)} CTR
                    </span>
                  </div>
                  <div>
                    <span className="ws4-rail-card__label">Rendered on article views (30d)</span>
                    <span className="ws4-rail-card__value">
                      {cov && cov.coverage !== null
                        ? `${pct(cov.coverage, 0)} of ${cov.articleViews30d.toLocaleString()} article views`
                        : 'No article views recorded in this window'}
                    </span>
                  </div>
                </div>

                <div className="ws4-position-chart" role="img" aria-label={`Clicks by position for ${rail.rail}`}>
                  {rail.clicksByPosition30d.map(({ position, clicks }) => (
                    <div className="ws4-position-bar" key={position}>
                      <div className="ws4-position-bar__track">
                        <div
                          className={`ws4-position-bar__fill ${clicks === 0 ? 'ws4-position-bar__fill--zero' : ''}`}
                          style={{ height: `${clicks === 0 ? 4 : Math.max(6, (clicks / maxPositionClicks) * 100)}%` }}
                        />
                      </div>
                      <span className="ws4-position-bar__n">{clicks}</span>
                      <span className="ws4-position-bar__label">{position}</span>
                    </div>
                  ))}
                </div>
                <p className="ws4-hint">Clicks by slot position, 1–6, last 30 days — position bias is real if this leans left.</p>
              </>
            ) : (
              <p className="console__sub">
                No impressions or clicks recorded for this rail in the last 30 days. Once the site
                serves it, its numbers appear here automatically.
              </p>
            )}
          </div>
        )
      })}

      <h2>Experiments</h2>
      <p className="platform__sub">
        Rails currently split by variant — the engine writes <code>&lt;rail&gt;~&lt;variant&gt;</code>{' '}
        while a test runs; no suffix means no experiment. Grouped and compared here automatically.
      </p>

      {experiments.length === 0 ? (
        <div className="console__empty">No rail is running an experiment right now.</div>
      ) : (
        experiments.map((exp) => (
          <div className="ws4-rail-card" key={exp.baseRail}>
            <h3>{exp.baseRail}</h3>
            <table className="platform__table">
              <thead>
                <tr>
                  <th>Variant</th>
                  <th>Impressions (30d)</th>
                  <th>Clicks (30d)</th>
                  <th>CTR</th>
                </tr>
              </thead>
              <tbody>
                {exp.arms.map((arm) => (
                  <tr key={arm.variant}>
                    <td>{arm.variant}</td>
                    <td>{arm.impressions30d.toLocaleString()}</td>
                    <td>{arm.clicks30d.toLocaleString()}</td>
                    <td>{pct(arm.ctr30d)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {exp.arms.length !== 2 ? (
              <p className="console__sub">
                {exp.arms.length} variants — comparing more than two arms to one p-value has no single
                right pairing, so only the counts above are shown.
              </p>
            ) : exp.comparison ? (
              exp.comparison.enoughData ? (
                <p className="ws4-experiment-verdict">
                  <strong>{pct(exp.comparison.test.rateB - exp.comparison.test.rateA)} difference</strong> between{' '}
                  <code>{exp.comparison.variant}</code> and <code>{exp.comparison.control}</code>, p ={' '}
                  {exp.comparison.test.pValue < 0.001 ? '<0.001' : exp.comparison.test.pValue.toFixed(3)}.{' '}
                  {exp.comparison.test.pValue < 0.05 ? 'Likely a real difference.' : 'Not a significant difference yet.'}
                </p>
              ) : (
                <p className="ws4-experiment-verdict ws4-experiment-verdict--pending">
                  Not enough readers yet: {plural(exp.comparison.totalClicksSoFar, 'click', 'clicks')}, needs ~
                  {exp.comparison.requiredPerVariant.toLocaleString()} impressions per variant to reliably call a
                  2-point difference.
                </p>
              )
            ) : (
              <p className="console__sub">One of the two variants has no impressions yet — nothing to compare.</p>
            )}
          </div>
        ))
      )}

      <h2>Tracking health</h2>
      <p className="platform__sub">Events per day, last 30 days — impressions and interactions combined.</p>

      {health.quiet ? (
        <div className="platform__notice platform__notice--bad">
          <p>
            {health.lastEventAt
              ? `The beacon has been quiet for ${plural(health.daysSinceLastEvent ?? 0, 'day', 'days')} — last event ${new Date(health.lastEventAt).toISOString().slice(0, 16).replace('T', ' ')} UTC.`
              : 'No event has ever been recorded for this city.'}
          </p>
        </div>
      ) : null}

      <div className="ws4-day-chart" role="img" aria-label="Events per day, last 30 days">
        {health.days.map((d) => (
          <div className="ws4-day-bar" key={d.day} title={`${d.day}: ${d.events} event(s)`}>
            <div
              className={`ws4-day-bar__fill ${d.events === 0 ? 'ws4-day-bar__fill--zero' : ''}`}
              style={{ height: `${d.events === 0 ? 3 : Math.max(4, (d.events / maxDayEvents) * 100)}%` }}
            />
          </div>
        ))}
      </div>
      <p className="ws4-hint">
        {health.days[0]?.day} to {health.days[health.days.length - 1]?.day}. A day with no bar is a real gap in the
        beacon, not a rendering issue.
      </p>
    </>
  )
}
