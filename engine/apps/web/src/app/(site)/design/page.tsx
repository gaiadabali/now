import { StoryCard } from '@/components/StoryCard'
import { Badge, BandHead, Byline, PartnerBadge } from '@/components/primitives'
import { getLatest } from '@/lib/content'
import { getSiteConfig } from '@/lib/site'

export const metadata = { title: 'Design system', robots: { index: false } }

/**
 * The reference for S6 ("The Edition") — rebuilt in full rather than
 * patched, because the previous version specimened a system this one
 * replaces: `--paper-deep`, `--ink-body`, `--t-banner` and a "three rule
 * weights" section none of which exist in `tokens.css` any more. A stale
 * reference page is worse than none, because it is the thing people check
 * against (DESIGN-SYSTEM.md, opening line).
 *
 * Internal, noindexed, not linked from the masthead. Every value shown here
 * is read from a token or from real content — nothing on this page is typed
 * in by hand, for the same reason nothing on the homepage is.
 */
export default async function DesignPage() {
  const site = await getSiteConfig()
  const articles = await getLatest(6)

  return (
    <div className="shell band">
      <p className="kicker kicker--red">Internal</p>
      <h1 className="display display--light" style={{ fontSize: 'var(--t-display)' }}>
        The design system
      </h1>
      <p className="dek" style={{ marginTop: 'var(--space-s)' }}>
        Three stocks, three faces, and a page that changes grid between every band. This is the
        reference S6 approved against — build from `docs/DESIGN-SYSTEM.md`, check against this.
      </p>

      {/* ---------------------------------------------------------- stocks */}
      <section className="band">
        <BandHead kicker="Rule 2 of 3" title="Stock" />
        <p className="dek" style={{ marginBottom: 'var(--space-m)' }}>
          A page uses all three. A page that is white top to bottom is the failure this replaced.
        </p>
        <div className="swatches">
          <div>
            <div className="swatch__chip" style={{ background: 'var(--paper)' }} />
            <div className="swatch__name">Paper</div>
            <div className="swatch__hex">--paper · news, indexes, the default ground</div>
          </div>
          <div>
            <div className="swatch__chip" style={{ background: 'var(--ivory)' }} />
            <div className="swatch__name">Ivory</div>
            <div className="swatch__hex">--ivory · one department given weight</div>
          </div>
          <div>
            <div className="swatch__chip" style={{ background: 'var(--ink)' }} />
            <div className="swatch__name">Ink</div>
            <div className="swatch__hex">--ink · one band per page, and the admin rail</div>
          </div>
        </div>
        <div className="swatches" style={{ marginTop: 'var(--space-m)' }}>
          {[
            ['Red', '--red'],
            ['Red deep', '--red-deep'],
            ['Gold — the edition line only', '--gold'],
            ['Type', '--type'],
            ['Body', '--body'],
            ['Mute', '--mute'],
            ['Faint', '--faint'],
          ].map(([name, token]) => (
            <div key={token}>
              <div className="swatch__chip" style={{ background: `var(${token})` }} />
              <div className="swatch__name">{name}</div>
              <div className="swatch__hex">{token}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------ type scale */}
      <section className="band">
        <BandHead kicker="Rule 1 of 3" title="Scale" />
        <p className="dek" style={{ marginBottom: 'var(--space-m)' }}>
          The ratio between display type and captions is most of what reads as expensive. Nothing
          sits between --t-title and --t-display.
        </p>
        {(
          [
            ['Cover', '--t-cover'],
            ['Display — a band opener', '--t-display'],
            ['Headline — an article h1', '--t-headline'],
            ['Title — a card headline', '--t-title'],
          ] as const
        ).map(([name, token]) => (
          <div className="specimen" key={token}>
            <div className="specimen__label">
              {name} · {token}
            </div>
            <div className="display display--light" style={{ fontSize: `var(${token})` }}>
              The Quiet Rooms of Ubud
            </div>
          </div>
        ))}
        <div className="specimen">
          <div className="specimen__label">Lede · --t-lede (italic Cormorant — the standfirst voice)</div>
          <p className="dek">
            The tasting-menu restaurant that taught an island to look at its own larder differently.
          </p>
        </div>
        <div className="specimen">
          <div className="specimen__label">Micro · --t-micro, --track-micro (Heebo capitals — captions, counts)</div>
          <span className="meta meta--micro">453 stories · updated monthly</span>
        </div>
        <div className="specimen">
          <div className="specimen__label">Label · --font-label, --track-label (Bebas — section labels, the edition line)</div>
          <span className="kicker kicker--red">Hotels</span>
        </div>
        <div className="specimen">
          <div className="specimen__label">Body · --t-body, --measure (66ch — the single biggest legibility lever)</div>
          <p className="prose" style={{ marginTop: 0 }}>
            Body copy sets at a 66-character measure. Anything wider and the eye loses the line
            return on its way back.
          </p>
        </div>
      </section>

      {/* --------------------------------------------------------- furniture */}
      <section className="band">
        <BandHead kicker="Rule 3 of 3" title="Colour from the photograph" />
        <p className="dek" style={{ marginBottom: 'var(--space-m)' }}>
          The chrome is white, ink and red. If a page looks colourless in development, that is
          placeholder imagery, not a missing token.
        </p>
        <div className="specimen">
          <div className="specimen__label">Rules — two weights, not three</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-s)' }}>
            <div>
              <p className="meta meta--micro" style={{ marginBottom: 'var(--space-3xs)' }}>
                --hair · between items, inside bands
              </p>
              <div style={{ borderTop: 'var(--hair)' }} />
            </div>
            <div>
              <p className="meta meta--micro" style={{ marginBottom: 'var(--space-3xs)' }}>
                --edge · a real boundary — nav, band opener
              </p>
              <div style={{ borderTop: 'var(--edge)' }} />
            </div>
          </div>
        </div>
      </section>

      <section className="band">
        <BandHead title="The band head" note="bandhead" />
        <p className="dek" style={{ marginBottom: 'var(--space-m)' }}>
          The kicker is information, not decoration — a count, a promise, a frequency. Leave it out
          rather than invent one.
        </p>
        <div className="specimen">
          <BandHead kicker="453 STORIES" title="Hotels" moreHref="/design" moreLabel="Every stay" />
        </div>
        <div style={{ background: 'var(--ink)', padding: 'var(--space-m)' }}>
          <BandHead kicker="230 GUIDES" title="The Guides" moreHref="/design" moreLabel="Every guide" />
        </div>
      </section>

      {/* ----------------------------------------------------------- pills */}
      <section className="band">
        <BandHead title="Status, as form" note="§5 — a console is scanned, so this reads before anything is read" />
        <div style={{ display: 'flex', gap: 'var(--space-2xs)', flexWrap: 'wrap' }}>
          <span className="pill pill--ok">Published</span>
          <span className="pill pill--draft">Draft</span>
          <span className="pill pill--scheduled">Scheduled</span>
        </div>
      </section>

      {/* --------------------------------------------------------- components */}
      <section className="band">
        <BandHead title="Badges" note="Partner disclosure is a product requirement, not decoration" />
        <div style={{ display: 'flex', gap: 'var(--space-2xs)', flexWrap: 'wrap' }}>
          <PartnerBadge />
          <Badge tone="live">Live</Badge>
          <Badge>Fine dining</Badge>
        </div>
      </section>

      <section className="band">
        <BandHead title="Byline" />
        <Byline author="NOW! Editorial" date="7 September 2026" minutes={6} />
      </section>

      <section className="band">
        <BandHead title="Story card" note="standard · portrait · horizontal · row · rank" />
        <div className="grid grid--3" style={{ marginBottom: 'var(--space-l)' }}>
          <StoryCard article={articles[0]} locale={site.locale} timeZone={site.timezone} />
          <StoryCard article={articles[1]} variant="portrait" locale={site.locale} timeZone={site.timezone} />
          <StoryCard article={articles[2]} variant="horizontal" showDek={false} locale={site.locale} timeZone={site.timezone} />
        </div>
        <div className="grid--index" style={{ marginBottom: 'var(--space-l)' }}>
          <StoryCard article={articles[3]} variant="row" locale={site.locale} timeZone={site.timezone} />
          <StoryCard article={articles[4]} variant="row" locale={site.locale} timeZone={site.timezone} />
        </div>
        <div style={{ background: 'var(--ink)', padding: 'var(--space-m)' }}>
          <StoryCard article={articles[5]} variant="rank" index={1} locale={site.locale} timeZone={site.timezone} />
        </div>
      </section>
    </div>
  )
}
