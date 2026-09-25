import 'server-only'

import { decodeEntities } from '@/lib/html'
import { cityPool } from '@/lib/payload'
import { facetTerms } from '@/lib/classification'

/**
 * The review queue, grouped the way the mistakes actually come.
 *
 * WHY THIS MODULE EXISTS AT ALL — the measurement that decided the design.
 * Bali's queue holds 6,485 pending classification proposals across 3,352
 * articles. Reviewed one row at a time, at a genuinely fast ten seconds a
 * decision, that is eighteen hours of someone's life. So I looked at what the
 * rows actually contain before building a faster way to click through them,
 * and they are not 6,485 different problems:
 *
 *     GROUP BY facet_key, legacy_category, proposed_value  ->  345 groups
 *
 * The top thirty of those cover about 60% of the queue, and several are a
 * single systematic error repeated hundreds of times:
 *
 *     164 articles   WP category "News"              -> type = stay   (41%)
 *      97 articles   WP category "Shopping"          -> format = news (41%)
 *      82 articles   WP category "Restaurants and Bars" -> format = news (42%)
 *      75 articles   WP category "Experience Offers" -> type = stay   (42%)
 *
 * A human does not need to see 164 articles to know that a news post is not
 * a place to stay. They need to see the *rule* the classifier applied, a few
 * examples to check it against, and one button. That is the whole design:
 * the unit of review is the pattern, not the row.
 *
 * The rejected alternative was the obvious one — a keyboard-driven single-row
 * decider, j/k/a/c, as fast as the hands can go. It is a better tool for a
 * queue of genuinely independent judgements. This queue is not that, and
 * building it would have meant optimising the eighteen hours instead of
 * removing them. The per-row controls still exist on the cluster page, for
 * the exceptions, which is where individual judgement is actually worth
 * spending.
 *
 * WHAT A CLUSTER IS, PRECISELY. `(facet_key, legacy_category, proposed_value)`
 * — the facet under review, the WordPress category the classifier used as its
 * prior (ARCHITECTURE.md §6: "classify... WP category = prior"), and what it
 * proposed. Confidence is deliberately NOT part of the key: within a cluster
 * it is near-constant anyway (it is a function of the same prior), and
 * splitting on it would shatter clean groups into noise.
 *
 * Read-only, every query here. The one write this feature makes goes through
 * Payload's Local API in the route's server action, because a decision has to
 * run the collection's hooks — they are what writes the article's own field
 * and announces `classification.reviewed` to the engine. Writing these rows
 * with SQL would record the decision and tell nobody.
 */

/** Only articles have pending reviews in either city, and only articles have
 * a readable title to show beside a proposal. Places would need their own
 * surface; asserting the filter here beats a join that silently returns rows
 * with no title. */
const ENTITY_TYPE = 'article'

export type ReviewCluster = {
  facetKey: string
  legacyCategory: string
  proposedValue: string
  pending: number
  meanConfidence: number | null
  minConfidence: number | null
  maxConfidence: number | null
  /**
   * How many distinct reasonings the classifier gave inside this cluster.
   * More than one means it arrived at the same answer by more than one route,
   * which is a reason to read before accepting the whole group.
   */
  reasonings: number
  sampleTitles: string[]
  /**
   * False when `proposedValue` is not a term in this facet's vocabulary at
   * all — in which case the proposal cannot be accepted, only corrected or
   * marked unclassifiable. Bali has 666 such rows: `subtype = unresolved`,
   * a value the classifier emits and the taxonomy has never contained.
   */
  proposalIsTerm: boolean
}

export type ClusterKey = {
  facetKey: string
  legacyCategory: string
  proposedValue: string
}

/**
 * Every pending cluster, biggest first.
 *
 * One statement, because the sample titles are the expensive part if fetched
 * per cluster: a window function partitions the pending set once and the
 * `FILTER (WHERE rn <= 3)` picks the three shakiest of each group out of the
 * same pass. 345 round trips became one.
 *
 * `ORDER BY confidence NULLS FIRST` inside the window, so the examples shown
 * are the cluster's *weakest* members. Showing its best would be a demo
 * rather than a check.
 */
export async function getReviewClusters(): Promise<ReviewCluster[]> {
  const [{ rows }, vocab] = await Promise.all([
    cityPool().query(
      `WITH pending AS (
         SELECT r.facet_key, r.legacy_category, r.proposed_value,
                r.confidence, r.reasoning, a.title,
                row_number() OVER (
                  PARTITION BY r.facet_key, r.legacy_category, r.proposed_value
                  ORDER BY r.confidence NULLS FIRST, r.id
                ) AS rn
           FROM public.classification_reviews r
           JOIN public.classification_reviews_rels rel ON rel.parent_id = r.id
           JOIN public.articles a ON a.id = rel.articles_id
          WHERE r.review_state = 'pending' AND r.entity_type = $1
       )
       SELECT facet_key, legacy_category, proposed_value,
              count(*)::int              AS pending,
              avg(confidence)::float8    AS mean_conf,
              min(confidence)::float8    AS min_conf,
              max(confidence)::float8    AS max_conf,
              count(DISTINCT reasoning)::int AS reasonings,
              array_remove(
                array_agg(title ORDER BY rn) FILTER (WHERE rn <= 3), NULL
              ) AS sample_titles
         FROM pending
        GROUP BY 1, 2, 3
        ORDER BY pending DESC, facet_key, legacy_category`,
      [ENTITY_TYPE],
    ),
    vocabularySlugs(),
  ])

  return rows.map((r) => ({
    facetKey: String(r.facet_key),
    legacyCategory: String(r.legacy_category ?? ''),
    proposedValue: String(r.proposed_value),
    pending: Number(r.pending),
    meanConfidence: r.mean_conf === null ? null : Number(r.mean_conf),
    minConfidence: r.min_conf === null ? null : Number(r.min_conf),
    maxConfidence: r.max_conf === null ? null : Number(r.max_conf),
    reasonings: Number(r.reasonings),
    sampleTitles: (r.sample_titles ?? []).map((t: unknown) => decodeEntities(String(t))),
    proposalIsTerm: vocab.get(String(r.facet_key))?.has(String(r.proposed_value)) ?? false,
  }))
}

/**
 * Slugs per facet, for "is this proposal even a term".
 *
 * Only the facets the queue actually uses are looked up, and only once per
 * render — `facetTerms` is a platform-database round trip and the queue has
 * three facets in it, not eleven.
 */
async function vocabularySlugs(): Promise<Map<string, Set<string>>> {
  const { rows } = await cityPool().query(
    `SELECT DISTINCT facet_key FROM public.classification_reviews WHERE review_state = 'pending'`,
  )
  const facets = rows.map((r) => String(r.facet_key))
  const loaded = await Promise.all(facets.map(async (f) => [f, await facetTerms(f)] as const))
  return new Map(loaded.map(([f, terms]) => [f, new Set(terms.map((t) => t.slug))]))
}

export type ClusterMember = {
  reviewId: number
  articleId: number
  title: string
  dek: string | null
  status: string
  publishedAt: string | null
  confidence: number | null
  reasoning: string
  /** What the article's own field says today — the value this decision replaces. */
  storedValue: string | null
}

export type ClusterDetail = {
  key: ClusterKey
  pending: number
  meanConfidence: number | null
  /** Distinct reasonings, verbatim, so a reviewer can read the rule itself. */
  reasonings: Array<{ text: string; count: number }>
  members: ClusterMember[]
  proposalIsTerm: boolean
  /** The facet's vocabulary, for the "correct the whole cluster to…" control. */
  terms: Array<{ slug: string; label: string; parentLabel: string | null }>
  /** The column on `articles` this facet writes, or null if it writes none. */
  targetField: string | null
}

/**
 * `articles` columns that a decided facet lands on, mirroring
 * `packages/cms/src/hooks/reviewQueueHooks.ts`'s `FIELD_MAP` for the article
 * half of it.
 *
 * Duplicated rather than imported, and that is a real trade-off I chose
 * knowingly: importing would drag the CMS package's hook module — and with it
 * Payload's runtime — into a plain SQL read. What it buys is the ability to
 * say, on screen, "`subtype` has no column on an article; this decision is
 * recorded and sent to the engine and changes nothing you can see in the edit
 * form" — which is true of 2,941 of Bali's 6,485 pending rows, and is the
 * kind of thing a reviewer should be told before spending an afternoon on it,
 * not after. If the map there gains an article entry, this must follow.
 */
const ARTICLE_FIELD: Record<string, string | null> = {
  type: 'primary_type',
  format: 'format',
  subtype: null,
  location: null,
}

/** How many of a cluster's articles the workbench lists. A reviewer checks a
 * pattern against a handful of examples and then decides; listing 666 of them
 * would be a different, slower claim about how this work is done. */
export const CLUSTER_SAMPLE = 40

/**
 * How many rows one press of a bulk button decides. Lives here rather than in
 * the server action beside the loop it bounds, because a `'use server'` module
 * may only export async functions — and the page has to state the number on
 * screen before the reviewer presses anything.
 *
 * Chosen against the clock, and then measured rather than guessed. Each row
 * runs the collection's hooks — an article write that creates a draft version,
 * plus a domain event — which is about 0.14s of work; four at a time made a
 * real 21-row cluster take 0.73s end to end, so 35ms a row. 250 is therefore
 * under ten seconds on this hardware, and most clusters are one press.
 *
 * Not the whole cluster in one request, however fast it looks locally. The
 * measurement above is a laptop talking to Postgres over loopback; production
 * is one box running the API, the worker and two Payload instances, and the
 * failure it would buy is a gateway timeout partway through a 666-row apply
 * with no way to tell how far it got. A bounded batch always reports exactly
 * what it did.
 */
export const BULK_BATCH = 250

export async function getCluster(key: ClusterKey): Promise<ClusterDetail | null> {
  const targetField = ARTICLE_FIELD[key.facetKey] ?? null

  // The article's current value for this facet, selected dynamically — from
  // the closed map above, never from the URL. `key.facetKey` reaches this
  // function from a query string, so the column name is chosen by lookup and
  // an unknown facet yields NULL rather than a string this code pastes into
  // SQL.
  const storedExpr = targetField ? `a.${targetField}::text` : 'NULL::text'

  const params = [key.facetKey, key.legacyCategory, key.proposedValue, ENTITY_TYPE]

  const [summary, members] = await Promise.all([
    cityPool().query(
      // Reasonings are normalised before grouping. The classifier appends the
      // winning cue's margin to its explanation — "scored 'stay' with margin
      // 1.30" — so six rows that applied one identical rule arrive as six
      // distinct strings, and the panel that is supposed to show a reviewer
      // *the rule* would instead show them arithmetic. Only the number is
      // collapsed; nothing else about the sentence is touched.
      `SELECT regexp_replace(reasoning, 'margin [0-9.]+', 'margin n') AS reasoning,
              count(*)::int AS reason_count, avg(confidence)::float8 AS mean_conf
         FROM public.classification_reviews
        WHERE review_state = 'pending' AND facet_key = $1
          AND legacy_category = $2 AND proposed_value = $3 AND entity_type = $4
        -- Positional, and it has to be. "GROUP BY reasoning" looks like it
        -- groups by the normalised value above and does not: Postgres resolves
        -- an ambiguous bare name in GROUP BY to the INPUT column, so it grouped
        -- by the raw text and the normalisation only renamed the survivors --
        -- six groups where there were two, and React duly complained about the
        -- duplicate keys. "1" is unambiguously the output column.
        GROUP BY 1
        ORDER BY reason_count DESC`,
      params,
    ),
    cityPool().query(
      `SELECT r.id AS review_id, a.id AS article_id, a.title, a.dek, a._status AS status,
              a.published_at, r.confidence::float8 AS confidence, r.reasoning,
              ${storedExpr} AS stored_value
         FROM public.classification_reviews r
         JOIN public.classification_reviews_rels rel ON rel.parent_id = r.id
         JOIN public.articles a ON a.id = rel.articles_id
        WHERE r.review_state = 'pending' AND r.facet_key = $1
          AND r.legacy_category = $2 AND r.proposed_value = $3 AND r.entity_type = $4
        ORDER BY r.confidence NULLS FIRST, r.id
        LIMIT ${CLUSTER_SAMPLE}`,
      params,
    ),
  ])

  if (summary.rows.length === 0) return null

  const terms = await facetTerms(key.facetKey)
  // `count(*)` in the grouped query counts per reasoning, so the cluster total
  // is their sum — not `summary.rows[0].pending`, which is only the largest
  // group's. A subtle one: with a single reasoning the two are equal, which is
  // exactly how a bug like that survives testing.
  const pending = summary.rows.reduce((n, r) => n + Number(r.reason_count), 0)
  const weighted = summary.rows.reduce(
    (acc, r) => (r.mean_conf === null ? acc : acc + Number(r.mean_conf) * Number(r.reason_count)),
    0,
  )

  return {
    key,
    pending,
    meanConfidence: pending === 0 ? null : weighted / pending,
    reasonings: summary.rows.map((r) => ({
      text: String(r.reasoning ?? ''),
      count: Number(r.reason_count),
    })),
    members: members.rows.map((r) => ({
      reviewId: Number(r.review_id),
      articleId: Number(r.article_id),
      title: decodeEntities(String(r.title ?? '')),
      dek: r.dek === null ? null : String(r.dek),
      status: String(r.status ?? ''),
      publishedAt: r.published_at === null ? null : new Date(r.published_at).toISOString(),
      confidence: r.confidence === null ? null : Number(r.confidence),
      reasoning: String(r.reasoning ?? ''),
      storedValue: r.stored_value === null ? null : String(r.stored_value),
    })),
    proposalIsTerm: terms.some((t) => t.slug === key.proposedValue),
    terms: terms.map((t) => ({ slug: t.slug, label: t.label, parentLabel: t.parentLabel })),
    targetField,
  }
}

/**
 * The review ids a bulk decision is allowed to touch, re-derived on the
 * server from the cluster key at apply time.
 *
 * NOT taken from the form. The form carries a cluster key — three short
 * strings — and the ids are looked up again here, so a tampered post can only
 * ever name a cluster, never a list of rows. It also means a row someone else
 * decided in the last minute has already left `review_state = 'pending'` and
 * is simply not in this result: the bulk apply is defined as "whatever of
 * this pattern is still undecided", which is the only definition that behaves
 * sensibly with two people working the same queue.
 */
export async function pendingIdsForCluster(key: ClusterKey, limit: number): Promise<number[]> {
  const { rows } = await cityPool().query(
    `SELECT id FROM public.classification_reviews
      WHERE review_state = 'pending' AND facet_key = $1
        AND legacy_category = $2 AND proposed_value = $3 AND entity_type = $4
      ORDER BY confidence NULLS FIRST, id
      LIMIT $5`,
    [key.facetKey, key.legacyCategory, key.proposedValue, ENTITY_TYPE, limit],
  )
  return rows.map((r) => Number(r.id))
}

export type QueueShape = {
  pending: number
  decided: number
  clusters: number
  articlesPending: number
  /** The share of the queue the ten largest clusters account for. */
  topTenShare: number
}

/** The numbers the desk leads with — how much work there is, and how much of
 * it is the same work repeated. */
export async function getQueueShape(): Promise<QueueShape> {
  const { rows } = await cityPool().query(
    `WITH g AS (
       SELECT count(*)::int AS n
         FROM public.classification_reviews
        WHERE review_state = 'pending' AND entity_type = $1
        GROUP BY facet_key, legacy_category, proposed_value
     )
     SELECT
       (SELECT count(*)::int FROM public.classification_reviews
         WHERE review_state = 'pending' AND entity_type = $1) AS pending,
       (SELECT count(*)::int FROM public.classification_reviews
         WHERE review_state <> 'pending' AND entity_type = $1) AS decided,
       (SELECT count(DISTINCT rel.articles_id)::int
          FROM public.classification_reviews r
          JOIN public.classification_reviews_rels rel ON rel.parent_id = r.id
         WHERE r.review_state = 'pending') AS articles_pending,
       (SELECT count(*)::int FROM g) AS clusters,
       (SELECT coalesce(sum(n), 0)::int FROM (SELECT n FROM g ORDER BY n DESC LIMIT 10) t) AS top_ten`,
    [ENTITY_TYPE],
  )
  const r = rows[0] ?? {}
  const pending = Number(r.pending ?? 0)
  return {
    pending,
    decided: Number(r.decided ?? 0),
    clusters: Number(r.clusters ?? 0),
    articlesPending: Number(r.articles_pending ?? 0),
    topTenShare: pending === 0 ? 0 : Number(r.top_ten ?? 0) / pending,
  }
}
