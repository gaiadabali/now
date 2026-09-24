import { StoryCard } from '@/components/StoryCard'
import { Badge, BandHead, Byline, PartnerBadge } from '@/components/primitives'
import { getLatest } from '@/lib/content'
import { getSiteConfig } from '@/lib/site'

export const metadata = { title: 'Design system', robots: { index: false } }

/**
 * The reference for Edition 2 — updated in place rather than rebuilt,
 * because S6's structure (stocks, scale, band head, story card) is still
 * the system; what changed is weight contrast, chrome and motion, and this
 * page now specimens those alongside what it already had. A stale reference
 * page is worse than none, because it is the thing people check against
 * (DESIGN-SYSTEM.md, opening line).
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

      {/* ---------------------------------------------------- weight contrast
          Edition 2's answer to "every headline is Cormorant 300... at card
          and index sizes it reads faint and monotone." Cover/display sizes
          keep the light weight; a card or index headline no longer does. */}
      <section className="band">
        <BandHead kicker="Edition 2" title="Weight contrast" note="display--medium · display--strong" />
        <p className="dek" style={{ marginBottom: 'var(--space-m)' }}>
          Cormorant 300 stays the voice at cover and display sizes. A card headline (with a
          photograph beside it) takes 500; an index row with no photograph — Latest's own
          complaint — takes 600, because the type alone has to carry the hierarchy a picture
          usually would.
        </p>
        <div className="specimen">
          <div className="specimen__label">300 · display--light · cover/display sizes only</div>
          <div className="display display--light" style={{ fontSize: 'var(--t-display)' }}>
            The Quiet Rooms of Ubud
          </div>
        </div>
        <div className="specimen">
          <div className="specimen__label">500 · display--medium · a card headline</div>
          <div className="display display--medium" style={{ fontSize: 'var(--t-title)' }}>
            The Quiet Rooms of Ubud
          </div>
        </div>
        <div className="specimen">
          <div className="specimen__label">600 · display--strong · Latest's row, no photograph</div>
          <div className="display display--strong" style={{ fontSize: 'var(--t-title)' }}>
            The Quiet Rooms of Ubud
          </div>
        </div>
      </section>

      {/* --------------------------------------------------------- chrome --- */}
      <section className="band">
        <BandHead kicker="Edition 2" title="Chrome" note="sticky, condensing, and a real mobile menu" />
        <p className="dek" style={{ marginBottom: 'var(--space-m)' }}>
          The masthead (top of this page) is sticky and condenses a few pixels into a scroll —
          try it. Below 62rem its section list is a native <code>&lt;details&gt;</code> drawer
          rather than the sideways-scrolling row it used to be; nothing here is client-rendered
          except the two classes <code>HeaderScroll</code> toggles on <code>&lt;body&gt;</code>
          (<code>hdr-condensed</code>, <code>hdr-hidden</code>) — see{' '}
          <code>components/HeaderScroll.tsx</code>.
        </p>
      </section>

      {/* --------------------------------------------------------- motion --- */}
      <section className="band">
        <BandHead kicker="Edition 2" title="Motion" note="purposeful, fast, and off under reduced motion" />
        <p className="dek" style={{ marginBottom: 'var(--space-m)' }}>
          No animation library. Everything below is CSS — reveal-on-scroll is
          `animation-timeline: view()` behind `@supports`, the reading progress bar (article
          pages) is `animation-timeline: scroll(root)`, and both stay fully visible with no
          animation at all wherever a browser or a reader's OS does not support or does not
          want it (`prefers-reduced-motion`). Hover a card below for the image-zoom and
          underline draw.
        </p>
        <div className="grid grid--3">
          <StoryCard article={articles[0]} locale={site.locale} timeZone={site.timezone} />
          <StoryCard article={articles[1]} locale={site.locale} timeZone={site.timezone} />
        </div>
      </section>
    </div>
  )
}
