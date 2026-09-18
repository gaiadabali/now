import Link from 'next/link'
import { notFound } from 'next/navigation'

import { requireReviewerAccess } from '@/lib/auth'
import { readBody } from '@/lib/bodyBlocks'
import {
  CONFIDENCE_GATE,
  facetTerms,
  getArticleClassification,
  reviewIdsForArticle,
} from '@/lib/classification'
import { decodeEntities, stripTags } from '@/lib/html'
import { payloadClient } from '@/lib/payload'

import { ArticleProse } from '../ArticleProse'
import { ConfidenceMeter } from '../ConfidenceMeter'
import { articleEditHref, classifyHref, reviewEditHref } from '../paths'
import { DecisionForm, type ReviewOption } from './DecisionForm'

/**
 * One `classification-reviews` row, as this page uses it.
 *
 * Hand-declared rather than imported, and that is a compromise worth naming.
 * `packages/cms/payload-types.ts` has the real generated `ClassificationReview`
 * interface — but that file is not in the package's `exports` map (only
 * `payload.config.ts` is), and it carries a `declare module 'payload'`
 * augmentation that would retype every Local API call in this app the moment
 * anything imports it. `lib/payload.ts` is deliberately written against a loose
 * `PayloadDoc`, so switching the whole app onto generated types is its own
 * change with its own verification, not a side effect of adding a report.
 *
 * What is NOT compromised: the string unions below are copied from the real
 * field `options` in `ClassificationReviews.ts`, so a value this page does not
 * expect is a type error here rather than a blank cell on screen. Lifting this
 * onto the generated type is the follow-up.
 */
type ReviewDoc = {
  id: number
  facetKey: 'type' | 'subtype' | 'format' | 'location'
  proposedValue: string
  finalValue?: string | null
  confidence: number
  reasoning?: string | null
  reviewState: 'pending' | 'accepted' | 'corrected' | 'unclassifiable'
  source?: 'ai' | 'editor' | 'inferred' | null
  legacyCategory?: string | null
  reviewedAt?: string | null
}

/**
 * The classification report for one article.
 *
 * WHY THIS IS A PAYLOAD CUSTOM VIEW AND NOT A TAB ON THE EDIT FORM.
 * A custom view *on the document* was the other candidate and it loses on
 * three counts, in increasing order of how much they matter:
 *   - It renders inside the document edit shell, one tab from the raw
 *     `body_blocks` JSON editor that is most of the reason this surface
 *     exists. The complaint was not "the edit form is missing a tab".
 *   - The data this page exists to show is in two databases neither of which
 *     Payload's document context can reach: `engine.entity_terms` is in the
 *     city DB but the `engine` schema, which Payload is forbidden to read
 *     (§1 principle 2), and the vocabulary that gives a `term_id` a meaning is
 *     in `now_platform` entirely. A server component can open both. A view
 *     bound to a Payload document cannot, and would have needed a custom
 *     endpoint behind it anyway — at which point the view is just a second
 *     way to reach the same server code.
 *   - It is one of four screens this report shares a chrome and a stylesheet
 *     with (S3.1) — the queue, the review desk, the cluster workbench — and
 *     none of the other three hang off a document.
 * So it is `admin.components.views` at the ROOT of the admin instead
 * (`ClassificationView.tsx`, one level up), which is the mechanism that gets
 * Payload's real sidebar rather than a document tab or a copy of the sidebar.
 * `articleEditHref` links back to the edit form for the fields this report
 * deliberately does not duplicate.
 *
 * FORMERLY `classification/[id]/page.tsx` — a literal Next dynamic route.
 * S3.1 folded it into `ClassificationView`'s dispatch, which is why `id`
 * arrives as a plain string rather than a Next.js `params` promise: the
 * dispatcher has already pulled it out of Payload's raw `segments` array
 * (there is no per-segment param name once the whole tree renders behind one
 * catch-all route — see `ClassificationView.tsx`).
 */
export async function ClassificationReportView({ id }: { id: string }) {
  await requireReviewerAccess()

  const articleId = Number(id)
  if (!Number.isInteger(articleId)) notFound()

  const payload = await payloadClient()

  // The published row, not the latest draft. The engine classified what is in
  // `public.articles`, and a report that showed an editor's unsaved rewording
  // beside a confidence computed from the old text would be describing two
  // different articles at once.
  const article = await payload
    .findByID({ collection: 'articles', id: articleId, depth: 0 })
    .catch(() => null)
  if (!article) notFound()

  const [report, reviewIds] = await Promise.all([
    getArticleClassification(articleId),
    reviewIdsForArticle(articleId),
  ])

  const reviews: ReviewDoc[] = reviewIds.length
    ? ((
        await payload.find({
          collection: 'classification-reviews',
          where: { id: { in: reviewIds } },
          sort: 'confidence',
          limit: 100,
          depth: 0,
        })
      ).docs as unknown as ReviewDoc[])
    : []

  const pending = reviews.filter((r) => r.reviewState === 'pending')
  const decided = reviews.filter((r) => r.reviewState !== 'pending')

  // One vocabulary fetch per distinct facet on screen, not one per review row:
  // an article commonly has a `type` and a `format` proposal and they would
  // otherwise pull the same 9 and 11 terms twice each.
  const facetKeys = [...new Set(pending.map((r) => r.facetKey))]
  const vocabulary = new Map<string, ReviewOption[]>(
    await Promise.all(
      facetKeys.map(async (key) => [key, await facetTerms(key)] as [string, ReviewOption[]]),
    ),
  )

  const body = readBody((article as { bodyBlocks?: unknown }).bodyBlocks)
  const title = decodeEntities(String((article as { title?: string }).title ?? '')) || `Article ${articleId}`
  const dek = stripTags(String((article as { dek?: string }).dek ?? ''))
  const status = String((article as { _status?: string })._status ?? 'draft')
  const primaryType = (article as { primaryType?: string | null }).primaryType ?? null
  const format = (article as { format?: string | null }).format ?? null
  const permalink = (article as { legacyPermalink?: string | null }).legacyPermalink ?? null

  return (
    <>
      <p className="classify__sub">
        <Link href={classifyHref()}>← Classification queue</Link>
      </p>

      <h1>{title}</h1>
      {dek ? <p className="classify__dek">{dek}</p> : null}

      <p className="classify__sub">
        <span className="classify__pill">{status}</span>{' '}
        <span className="classify__pill">
          type: {primaryType ?? 'not set'}
        </span>{' '}
        <span className="classify__pill">format: {format ?? 'not set'}</span>{' '}
        <Link href={articleEditHref(articleId)}>Open the edit form</Link>
        {permalink ? (
          <>
            {' · '}
            <a href={permalink} rel="noreferrer nofollow" target="_blank">
              original
            </a>
          </>
        ) : null}
      </p>

      {/* ---- what the engine decided ------------------------------------ */}

      <h2 className="classify__subhead">What the engine decided</h2>
      <p className="classify__sub">
        {report.total === 0 ? (
          <>
            Nothing. There is no row in <code>engine.entity_terms</code> for this
            article, so the classifier has never run over it — not the same
            thing as running and being unsure.
          </>
        ) : (
          <>
            {report.total} facet assignment{report.total === 1 ? '' : 's'},{' '}
            {report.belowGate > 0 ? (
              <strong>{report.belowGate} below the {CONFIDENCE_GATE} gate</strong>
            ) : (
              <>none below the {CONFIDENCE_GATE} gate</>
            )}
            {report.meanConfidence !== null ? (
              <> · mean confidence {report.meanConfidence.toFixed(2)}</>
            ) : null}
            . Least certain first.
          </>
        )}
      </p>

      {report.bySource.length > 0 ? (
        <div className="classify__cards classify__cards--tight">
          {report.bySource.map((s) => (
            <div className="classify__card" key={s.source}>
              <div className="classify__n">
                {s.count}
                {s.belowGate > 0 ? <span className="classify__n-sub"> · {s.belowGate} under gate</span> : null}
              </div>
              <div className="classify__k">
                <span className={`classify__prov classify__prov--${s.source}`}>{s.source}</span>
                {s.meanConfidence !== null ? ` mean ${s.meanConfidence.toFixed(2)}` : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {report.total > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Facet</th>
              <th>Value</th>
              <th>Confidence</th>
              <th>Provenance</th>
              <th className="classify__num">Weight</th>
              <th>Assigned</th>
            </tr>
          </thead>
          <tbody>
            {report.assignments.map((a) => (
              <tr
                key={`${a.termId}`}
                className={(a.confidence ?? 0) < CONFIDENCE_GATE ? 'classify__row--flag' : undefined}
              >
                <td>{a.facetLabel ?? <span className="classify__muted">unresolved</span>}</td>
                <td>
                  {a.termLabel ? (
                    <>
                      {a.termLabel}
                      {a.parentLabel ? <span className="classify__muted"> in {a.parentLabel}</span> : null}
                      <br />
                      <code className="classify__muted">{a.termSlug}</code>
                    </>
                  ) : (
                    <span className="classify__muted" title={a.termId}>
                      term {a.termId.slice(0, 8)}… is in no platform vocabulary row
                    </span>
                  )}
                </td>
                <td>
                  <ConfidenceMeter confidence={a.confidence} />
                </td>
                <td>
                  <span className={`classify__prov classify__prov--${a.source}`}>{a.source}</span>
                </td>
                <td className="classify__num">{a.weight.toFixed(2)}</td>
                <td className="classify__muted">{a.createdAt.slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      {report.missingRequiredFacets.length > 0 ? (
        <p className="classify__note">
          No assignment at all for{' '}
          {report.missingRequiredFacets.map((f) => f.label).join(', ')} — and the
          taxonomy marks {report.missingRequiredFacets.length === 1 ? 'that facet' : 'those facets'}{' '}
          required (§4). An absent facet is invisible to §8.A&rsquo;s filters, which
          is a different failure from a low-confidence one: nothing is wrong, and
          nothing is there.
        </p>
      ) : null}

      {report.unresolved > 0 ? (
        <p className="classify__note classify__note--flag">
          {report.unresolved}{' '}
          {report.unresolved === 1 ? 'assignment points' : 'assignments point'} at a
          term id that has no row in <code>now_platform.engine.terms</code>. The
          city database and the platform vocabulary have drifted; these tags
          cannot be rendered, filtered or reviewed until that is reconciled.
        </p>
      ) : null}

      {/* ---- the review queue for this article --------------------------- */}

      <h2 className="classify__subhead">Queued for review</h2>
      <p className="classify__sub">
        {reviews.length === 0 ? (
          <>
            No <code>classification-reviews</code> rows for this article. The
            review queue and <code>engine.entity_terms</code> are populated
            independently, so an article can carry below-gate assignments with
            nothing queued against them — a proposal is only reviewable here
            once E2.1 has written it a review row.
          </>
        ) : (
          <>
            A decision here is written with <code>source: &lsquo;editor&rsquo;</code> and
            stays permanently distinguishable from a guess — a classifier re-run
            is required to leave it alone. It is applied to the article&rsquo;s own
            field immediately and announced as a{' '}
            <code>classification.reviewed</code> domain event, which
            engine-worker consumes to rewrite the matching{' '}
            <code>engine.entity_terms</code> row as <code>editor</code> and
            retire the term it replaced. That last step is asynchronous, so the
            assignments above can read <code>ai</code> or <code>inferred</code>{' '}
            for a moment after a decision.
          </>
        )}
      </p>

      {pending.length > 0 ? (
        <ul className="classify__reviews">
          {pending.map((r) => {
            const options = vocabulary.get(r.facetKey) ?? []
            const proposedLabel = options.find((o) => o.slug === r.proposedValue)?.label
            return (
              <li key={r.id} className="classify__review">
                <div className="classify__review-head">
                  <span className="classify__review-facet">{r.facetKey}</span>
                  <strong>{proposedLabel ?? r.proposedValue}</strong>
                  <ConfidenceMeter confidence={Number(r.confidence)} />
                  <span className={`classify__prov classify__prov--${r.source ?? 'ai'}`}>
                    {r.source ?? 'ai'}
                  </span>
                  <Link className="classify__review-link" href={reviewEditHref(r.id)}>
                    row #{r.id}
                  </Link>
                </div>
                {r.reasoning ? <p className="classify__reasoning">{r.reasoning}</p> : null}
                {r.legacyCategory ? (
                  <p className="classify__muted">
                    Legacy WordPress category: <code>{r.legacyCategory}</code>
                  </p>
                ) : null}
                <DecisionForm
                  articleId={articleId}
                  reviewId={r.id}
                  proposedValue={r.proposedValue}
                  options={options}
                />
              </li>
            )
          })}
        </ul>
      ) : null}

      {decided.length > 0 ? (
        <table>
          {/* A caption, not another heading. It is the same section — a row
              that gets decided leaves the list above and lands here, and
              without something naming the boundary that move looks like the
              row simply vanished. */}
          <caption className="classify__caption">
            Already decided — these have left the queue
          </caption>
          <thead>
            <tr>
              <th>Facet</th>
              <th>Proposed</th>
              <th>Outcome</th>
              <th>Final</th>
              <th>Decided</th>
            </tr>
          </thead>
          <tbody>
            {decided.map((r) => (
              <tr key={r.id}>
                <td>{r.facetKey}</td>
                <td>
                  <code>{r.proposedValue}</code>
                </td>
                <td>
                  <span className="classify__pill">{r.reviewState}</span>
                </td>
                <td>{r.finalValue ? <code>{r.finalValue}</code> : <span className="classify__muted">—</span>}</td>
                <td className="classify__muted">
                  {r.reviewedAt ? r.reviewedAt.slice(0, 10) : '—'}
                  {r.source === 'editor' ? (
                    <> <span className="classify__prov classify__prov--editor">editor</span></>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      {/* ---- the article ------------------------------------------------- */}

      <h2 className="classify__subhead">The article</h2>
      <p className="classify__sub">
        {body.words.toLocaleString()} words across{' '}
        {body.counts.reduce((n, c) => n + c.count, 0).toLocaleString()} stored blocks
        {body.counts.length ? (
          <>
            {' '}
            ({body.counts.map((c) => `${c.count} ${c.type}`).join(', ')})
          </>
        ) : null}
        . This is the text the classifier read.
        {body.unhandled.length ? (
          <>
            {' '}
            <strong>
              Not shown: {body.unhandled.join(', ')} — block type
              {body.unhandled.length === 1 ? '' : 's'} this report has no renderer for.
            </strong>
          </>
        ) : null}
      </p>

      {body.blocks.length === 0 ? (
        <div className="classify__empty">This article has no stored body blocks.</div>
      ) : (
        <ArticleProse blocks={body.blocks} />
      )}
    </>
  )
}
