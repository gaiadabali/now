import 'server-only'

import { cityPool } from '@/lib/payload'
import { requiredSampleSizePerVariant, twoProportionZTest } from '@/lib/abStats'
import type { ZTestResult } from '@/lib/abStats'

/**
 * "How suggestions are doing" — the engine roadmap's "a dashboard of clicks
 * per rail, plus A/B tests", read from `engine.impressions` and
 * `engine.interactions` (ARCHITECTURE.md §5's E0.2 beacon contract).
 *
 * **Per city, like every other read in this console.** This process is
 * bound to one city's database (`cityPool()` / `DATABASE_URI` —
 * ARCHITECTURE.md §3.5's "one deliberate per-city knob"), the same fact
 * `facetCoverage.ts` labels rather than glosses over. Every figure below is
 * this city's own, and the view names the city on screen for the same
 * reason that file does.
 *
 * **The data is genuinely tiny today** — 38 interactions, 46 impressions,
 * all from one eight-minute window over a week ago (verified against the
 * real table, not assumed). That is not a fixture to work around; it is
 * the actual state of the beacon, and the whole point of "Tracking health"
 * below is to say so rather than hide it behind a chart that looks fine at
 * a glance.
 */

/**
 * The eight rails the ticket names. Always listed, even at zero — a rail
 * with no data yet is a real, current fact ("nothing has served this rail
 * in the window"), not a reason to hide the row. What must NOT happen is
 * inventing a number for it; every figure below comes straight out of a
 * `count(*)`.
 */
export const CANONICAL_RAILS = [
  'read-next',
  'plan-dining',
  'plan-stay',
  'plan-wellness',
  'plan-things-to-do',
  'plan-events',
  'for-you',
  'readers-also-read',
] as const

export type CanonicalRail = (typeof CANONICAL_RAILS)[number]

/**
 * WS1's A/B encoding: `<rail>~<variant>` while an experiment runs, no
 * suffix when it isn't. Split once, here, so every query downstream works
 * in terms of (baseRail, variant) and never has to know the encoding
 * exists.
 */
function splitRailVariant(raw: string): { baseRail: string; variant: string | null } {
  const i = raw.indexOf('~')
  if (i === -1) return { baseRail: raw, variant: null }
  return { baseRail: raw.slice(0, i), variant: raw.slice(i + 1) || null }
}

type RawCountRow = { rail: string; position: number | null; window_days: number; n: string }

async function countByRailAndWindow(
  table: 'engine.impressions' | 'engine.interactions',
  extraWhere: string,
): Promise<RawCountRow[]> {
  // One query, both windows, via two FILTERed COUNTs unioned into rows —
  // cheaper than two round trips, and it means the 7-day and 30-day figures
  // can never disagree about what "now" was.
  const { rows } = await cityPool().query<{ rail: string; position: number | null; n7: string; n30: string }>(
    `SELECT rail, position,
            count(*) FILTER (WHERE ts >= now() - interval '7 days')  AS n7,
            count(*) FILTER (WHERE ts >= now() - interval '30 days') AS n30
       FROM ${table}
      WHERE rail IS NOT NULL AND ts >= now() - interval '30 days' ${extraWhere}
      GROUP BY rail, position`,
  )
  const out: RawCountRow[] = []
  for (const r of rows) {
    out.push({ rail: r.rail, position: r.position, window_days: 7, n: r.n7 })
    out.push({ rail: r.rail, position: r.position, window_days: 30, n: r.n30 })
  }
  return out
}

export type VariantStats = {
  baseRail: string
  variant: string | null
  impressions7d: number
  impressions30d: number
  clicks7d: number
  clicks30d: number
  /** Clicks by position (1..6), 30-day window — the position-bias figure. */
  clicksByPosition30d: Record<number, number>
}

export type RailSummary = {
  rail: string
  impressions7d: number
  clicks7d: number
  ctr7d: number | null
  impressions30d: number
  clicks30d: number
  ctr30d: number | null
  clicksByPosition30d: Array<{ position: number; clicks: number }>
  hasData: boolean
}

export type ExperimentArm = {
  variant: string
  impressions30d: number
  clicks30d: number
  ctr30d: number | null
}

export type Experiment = {
  baseRail: string
  arms: ExperimentArm[]
  /** Only present when exactly 2 arms both have impressions — a 3+-arm
   *  comparison is shown as a table without a single p-value, since "B vs
   *  which?" has no single right answer to compute. */
  comparison: {
    control: string
    variant: string
    test: ZTestResult
    requiredPerVariant: number
    enoughData: boolean
    totalClicksSoFar: number
  } | null
}

export type CoverageRow = { rail: string; articleViews30d: number; coveredViews30d: number; coverage: number | null }

export type TrackingHealthDay = { day: string; events: number }
export type TrackingHealth = {
  days: TrackingHealthDay[]
  lastEventAt: string | null
  daysSinceLastEvent: number | null
  quiet: boolean
}

/** Fetches every (rail-string, position) count for both tables, splits the
 * rail string into (baseRail, variant), and folds it into one map keyed
 * `${baseRail}\u0000${variant ?? ''}`. */
async function loadVariantStats(): Promise<Map<string, VariantStats>> {
  const [impressionRows, clickRows] = await Promise.all([
    countByRailAndWindow('engine.impressions', ''),
    countByRailAndWindow("engine.interactions", "AND kind = 'click'"),
  ])

  const map = new Map<string, VariantStats>()
  const key = (baseRail: string, variant: string | null) => `${baseRail}\u0000${variant ?? ''}`
  const get = (baseRail: string, variant: string | null): VariantStats => {
    const k = key(baseRail, variant)
    let entry = map.get(k)
    if (!entry) {
      entry = { baseRail, variant, impressions7d: 0, impressions30d: 0, clicks7d: 0, clicks30d: 0, clicksByPosition30d: {} }
      map.set(k, entry)
    }
    return entry
  }

  for (const row of impressionRows) {
    const { baseRail, variant } = splitRailVariant(row.rail)
    const entry = get(baseRail, variant)
    if (row.window_days === 7) entry.impressions7d += Number(row.n)
    else entry.impressions30d += Number(row.n)
  }
  for (const row of clickRows) {
    const { baseRail, variant } = splitRailVariant(row.rail)
    const entry = get(baseRail, variant)
    if (row.window_days === 7) entry.clicks7d += Number(row.n)
    else {
      entry.clicks30d += Number(row.n)
      if (row.position !== null && row.position >= 1 && row.position <= 6) {
        entry.clicksByPosition30d[row.position] = (entry.clicksByPosition30d[row.position] ?? 0) + Number(row.n)
      }
    }
  }
  return map
}

function ctr(clicks: number, impressions: number): number | null {
  return impressions > 0 ? clicks / impressions : null
}

/** Every canonical rail, summed across whatever variants exist for it. */
export async function getRailSummaries(): Promise<RailSummary[]> {
  const variants = await loadVariantStats()
  const byBase = new Map<string, VariantStats[]>()
  for (const v of variants.values()) {
    const list = byBase.get(v.baseRail) ?? []
    list.push(v)
    byBase.set(v.baseRail, list)
  }

  const summaries: RailSummary[] = []
  for (const rail of CANONICAL_RAILS) {
    const arms = byBase.get(rail) ?? []
    const impressions7d = arms.reduce((s, a) => s + a.impressions7d, 0)
    const clicks7d = arms.reduce((s, a) => s + a.clicks7d, 0)
    const impressions30d = arms.reduce((s, a) => s + a.impressions30d, 0)
    const clicks30d = arms.reduce((s, a) => s + a.clicks30d, 0)
    const positions: Record<number, number> = {}
    for (const a of arms) {
      for (const [pos, n] of Object.entries(a.clicksByPosition30d)) {
        positions[Number(pos)] = (positions[Number(pos)] ?? 0) + n
      }
    }
    summaries.push({
      rail,
      impressions7d,
      clicks7d,
      ctr7d: ctr(clicks7d, impressions7d),
      impressions30d,
      clicks30d,
      ctr30d: ctr(clicks30d, impressions30d),
      clicksByPosition30d: [1, 2, 3, 4, 5, 6].map((position) => ({ position, clicks: positions[position] ?? 0 })),
      hasData: impressions30d > 0 || clicks30d > 0,
    })
  }
  return summaries
}

/**
 * Rails currently running an experiment — grouped by base rail, one row per
 * variant, with a two-proportion test between the two biggest arms when
 * there are exactly two. `requiredPerVariant` is the real power-calculation
 * figure (`requiredSampleSizePerVariant`), computed from THIS rail's own
 * control-arm CTR — not a fixed guess — for a 2-point absolute difference,
 * matching the ticket's own example.
 */
export async function getExperiments(): Promise<Experiment[]> {
  const variants = await loadVariantStats()
  const byBase = new Map<string, VariantStats[]>()
  for (const v of variants.values()) {
    if (v.variant === null) continue // no experiment suffix -> not a running test
    const list = byBase.get(v.baseRail) ?? []
    list.push(v)
    byBase.set(v.baseRail, list)
  }

  const experiments: Experiment[] = []
  for (const [baseRail, arms] of byBase) {
    const sorted = [...arms].sort((a, b) => b.impressions30d - a.impressions30d)
    const armSummaries: ExperimentArm[] = sorted.map((a) => ({
      variant: a.variant as string,
      impressions30d: a.impressions30d,
      clicks30d: a.clicks30d,
      ctr30d: ctr(a.clicks30d, a.impressions30d),
    }))

    let comparison: Experiment['comparison'] = null
    if (sorted.length === 2) {
      const [control, variant] = sorted
      const test = twoProportionZTest(control.clicks30d, control.impressions30d, variant.clicks30d, variant.impressions30d)
      if (test) {
        const baselineRate = control.clicks30d > 0 ? test.rateA : 0.02 // a real floor, not zero, so the figure is never "Infinity"
        const requiredPerVariant = requiredSampleSizePerVariant(baselineRate, 0.02)
        const smallerArmImpressions = Math.min(control.impressions30d, variant.impressions30d)
        comparison = {
          control: control.variant as string,
          variant: variant.variant as string,
          test,
          requiredPerVariant,
          enoughData: smallerArmImpressions >= requiredPerVariant,
          totalClicksSoFar: control.clicks30d + variant.clicks30d,
        }
      }
    }

    experiments.push({ baseRail, arms: armSummaries, comparison })
  }
  return experiments.sort((a, b) => a.baseRail.localeCompare(b.baseRail))
}

/**
 * "The share of article views where the rail rendered at all" —
 * approximated, honestly: `impressions` and `interactions` share a
 * `session_id` but no common page-load id, so a rail's impression is
 * counted as covering a given article view when it landed in the SAME
 * session within 30 seconds after the view fired (rails render on or
 * shortly after initial page load; 30s is generous, not tight). This is a
 * real, checkable proxy, not an exact join — the screen says so, the same
 * way `facetCoverage.ts` labels what its own number can and cannot claim.
 */
export async function getCoverage(): Promise<CoverageRow[]> {
  const { rows: viewRows } = await cityPool().query<{ n: string }>(
    `SELECT count(*) AS n FROM engine.interactions
      WHERE kind = 'view' AND entity_type = 'article' AND ts >= now() - interval '30 days'`,
  )
  const articleViews30d = Number(viewRows[0]?.n ?? 0)

  if (articleViews30d === 0) {
    return CANONICAL_RAILS.map((rail) => ({ rail, articleViews30d: 0, coveredViews30d: 0, coverage: null }))
  }

  const { rows } = await cityPool().query<{ base_rail: string; n: string }>(
    `WITH views AS (
       SELECT id, session_id, ts FROM engine.interactions
        WHERE kind = 'view' AND entity_type = 'article' AND ts >= now() - interval '30 days'
     )
     SELECT split_part(i.rail, '~', 1) AS base_rail, count(DISTINCT v.id) AS n
       FROM views v
       JOIN engine.impressions i
         ON i.session_id = v.session_id
        AND i.rail IS NOT NULL
        AND i.ts BETWEEN v.ts - interval '5 seconds' AND v.ts + interval '30 seconds'
      GROUP BY 1`,
  )
  const covered = new Map(rows.map((r) => [r.base_rail, Number(r.n)]))

  return CANONICAL_RAILS.map((rail) => {
    const coveredViews30d = covered.get(rail) ?? 0
    return { rail, articleViews30d, coveredViews30d, coverage: coveredViews30d / articleViews30d }
  })
}

/**
 * Events per day for 30 days (both tables combined — "events" here means
 * everything the beacon sent, impressions and interactions alike, which is
 * what "has the beacon gone quiet" actually asks), plus the quiet-day flag.
 */
export async function getTrackingHealth(): Promise<TrackingHealth> {
  const { rows } = await cityPool().query<{ day: string; n: string }>(
    `SELECT day::date::text AS day, sum(n)::text AS n FROM (
       SELECT date_trunc('day', ts) AS day, count(*) AS n
         FROM engine.impressions WHERE ts >= now() - interval '30 days' GROUP BY 1
       UNION ALL
       SELECT date_trunc('day', ts) AS day, count(*) AS n
         FROM engine.interactions WHERE ts >= now() - interval '30 days' GROUP BY 1
     ) combined
     GROUP BY day
     ORDER BY day`,
  )
  const byDay = new Map(rows.map((r) => [r.day, Number(r.n)]))

  const { rows: lastRows } = await cityPool().query<{ last_ts: string | null }>(
    `SELECT greatest(
        (SELECT max(ts) FROM engine.impressions),
        (SELECT max(ts) FROM engine.interactions)
     )::text AS last_ts`,
  )
  const lastEventAt = lastRows[0]?.last_ts ?? null
  const daysSinceLastEvent = lastEventAt ? Math.floor((Date.now() - new Date(lastEventAt).getTime()) / 86_400_000) : null

  const days: TrackingHealthDay[] = []
  const today = new Date()
  for (let i = 29; i >= 0; i--) {
    const d = new Date(today)
    d.setUTCDate(d.getUTCDate() - i)
    const key = d.toISOString().slice(0, 10)
    days.push({ day: key, events: byDay.get(key) ?? 0 })
  }

  return {
    days,
    lastEventAt,
    daysSinceLastEvent,
    // "Gone quiet for a day" — no event recorded since yesterday at this
    // time, i.e. more than a full day of silence, not merely "nothing since
    // midnight" which would false-alarm every single morning.
    quiet: daysSinceLastEvent === null || daysSinceLastEvent >= 1,
  }
}
