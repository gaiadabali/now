import { Band, BandHead } from '@/components/primitives'
import { StoryCard } from '@/components/StoryCard'
import type { ArticleRail } from '@/lib/recommend'

/**
 * How the article page renders `getArticleRails()`'s output — split out of
 * `[slug]/page.tsx` so the same markup can be driven by a local fixture on
 * `/design` (the sanctioned place to build against a shape the engine does
 * not return yet; never the live article page).
 *
 * The contract (`lib/recommend.ts`, WS1's): a venue story gets `read-next`
 * plus UP TO THREE `plan-<section>` rails — "Plan around it", each already
 * excluding the story's own competitor class. Rendering each as its own
 * full band would end a hotel story with four stacked 3-up bands, which
 * reads as four times "here is more content" rather than once. So this
 * groups every `plan-*` rail into ONE band with a column per rail, and
 * leaves `read-next` — the only rail every article gets, venue or not — as
 * the sole full-width band.
 *
 * Nothing here re-orders or re-picks what the engine returned; it only
 * decides which bands the already-chosen items are laid out inside.
 */

export function ReadNextBand({
  rail,
  locale,
  timeZone,
}: {
  rail: ArticleRail | undefined
  locale: string
  timeZone: string
}) {
  if (!rail || rail.items.length === 0) return null
  return (
    <Band reveal>
      <div className="shell">
        <BandHead kicker={rail.kicker} title={rail.title} />
        <div className="grid grid--3 grid--ruled">
          {/* Engine-ranked, so §10's position bias has to be corrected for
              — the slot is recorded on the impression AND the click. */}
          {rail.items.map((a) => (
            <StoryCard key={a.id} article={a} locale={locale} timeZone={timeZone} rail={a.rail} position={a.position} />
          ))}
        </div>
      </div>
    </Band>
  )
}

/**
 * Every `plan-*` rail, one column each — "3 compact items: small thumbnail
 * + headline + meta" per the brief, which is `card--horizontal` unchanged
 * (the same variant the lead package's secondaries and a department band's
 * side items already use, rather than a seventh StoryCard shape).
 *
 * `grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr))` is the
 * "degrades cleanly to 1, 2 or 3 columns" requirement done without a
 * breakpoint per count: 1-3 columns of at least 15rem each fit as many as
 * the viewport allows, and a phone — unable to fit two — collapses to one
 * automatically, no media query needed.
 */
export function PlanAroundBand({
  rails,
  locale,
  timeZone,
}: {
  rails: ArticleRail[]
  locale: string
  timeZone: string
}) {
  const withItems = rails.filter((r) => r.items.length > 0)
  if (withItems.length === 0) return null

  return (
    <Band tone="ivory" reveal>
      <div className="shell">
        {/* The shared kicker every `plan-*` rail carries ("Plan around it")
            IS the band's title here — there is no separate band-level
            concept beyond what the rails already agreed on, so this reads
            it from the data rather than a page-level literal that could
            drift from what the engine actually sends. */}
        <BandHead title={withItems[0].kicker} />
        <div className="grid--plan">
          {withItems.map((rail) => (
            <div className="plan-col" key={rail.key}>
              <p className="plan-col__head">{rail.title}</p>
              <div className="plan-col__items">
                {rail.items.map((a) => (
                  <StoryCard
                    key={a.id}
                    article={a}
                    variant="horizontal"
                    showDek={false}
                    locale={locale}
                    timeZone={timeZone}
                    rail={a.rail}
                    position={a.position}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Band>
  )
}
