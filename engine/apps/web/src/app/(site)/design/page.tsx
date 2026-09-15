import { StoryCard } from '@/components/StoryCard'
import { Badge, Byline, PartnerBadge, SectionRule } from '@/components/primitives'
import { getLatest } from '@/lib/content'
import { getSiteConfig } from '@/lib/site'

export const metadata = { title: 'Design system', robots: { index: false } }

const SWATCHES = [
  ['Paper', '--paper', '#fbf9f5'],
  ['Paper deep', '--paper-deep', '#f2ede3'],
  ['Ink', '--ink', '#1d1d1b'],
  ['Ink body', '--ink-body', '#2b2926'],
  ['Ink mute', '--ink-mute', '#6c6760'],
  ['Ink faint', '--ink-faint', '#a49d92'],
  ['Red', '--red', '#cd1719'],
  ['Red deep', '--red-deep', '#a01013'],
]

const SCALE = [
  ['Banner', '--t-banner', 'NOW!'],
  ['Display', '--t-display', 'The Quiet Rooms of Ubud'],
  ['Headline', '--t-headline', 'The Quiet Rooms of Ubud'],
  ['Title', '--t-title', 'The Quiet Rooms of Ubud'],
  ['Subtitle', '--t-subtitle', 'The Quiet Rooms of Ubud'],
]

/** Internal reference page. Noindexed; not linked from the masthead. */
export default async function DesignPage() {
  const site = await getSiteConfig()
  const articles = await getLatest(3)

  return (
    <div className="shell band">
      <p className="kicker kicker--red">Internal</p>
      <h1 className="display display--light" style={{ fontSize: 'var(--t-display)' }}>
        The design system
      </h1>
      <p className="dek" style={{ marginTop: 'var(--space-s)' }}>
        Cormorant and Heebo are the brand&rsquo;s own faces; the red is sampled from the logo. What
        changed is everything around them — Bootstrap&rsquo;s grey scale and chrome are gone, the
        ground is warm paper, and the page is held together by three rule weights instead of boxes.
      </p>

      <section className="band">
        <SectionRule label="Colour" note="Eight values. There is no ninth." />
        <div className="swatches">
          {SWATCHES.map(([name, token, hex]) => (
            <div key={token}>
              <div className="swatch__chip" style={{ background: `var(${token})` }} />
              <div className="swatch__name">{name}</div>
              <div className="swatch__hex">
                {token} · {hex}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="band">
        <SectionRule label="Type scale" note="Cormorant 300–500 · Heebo 400–700" />
        {SCALE.map(([name, token, sample]) => (
          <div className="specimen" key={token}>
            <div className="specimen__label">
              {name} · {token}
            </div>
            <div className="display display--light" style={{ fontSize: `var(${token})` }}>
              {sample}
            </div>
          </div>
        ))}
        <div className="specimen">
          <div className="specimen__label">Kicker · --t-meta</div>
          <span className="kicker">Dining / The Feature</span>
        </div>
        <div className="specimen">
          <div className="specimen__label">Dek · --t-dek (Cormorant italic)</div>
          <p className="dek">
            The tasting-menu restaurant that taught an island to look at its own larder differently.
          </p>
        </div>
        <div className="specimen">
          <div className="specimen__label">Body · --t-body, 66ch measure</div>
          <p className="prose" style={{ marginTop: 0 }}>
            Body copy sets at a 66-character measure, which is the single biggest legibility lever on
            a long-read site. Anything wider and the eye loses the line return.
          </p>
        </div>
      </section>

      <section className="band">
        <SectionRule label="Rules" note="Three weights. Never a fourth." />
        <div className="specimen">
          <div className="specimen__label">--rule-hair · between items</div>
          <div style={{ borderTop: 'var(--rule-hair)' }} />
        </div>
        <div className="specimen">
          <div className="specimen__label">--rule-thin · section boundary</div>
          <div style={{ borderTop: 'var(--rule-thin)' }} />
        </div>
        <div className="specimen">
          <div className="specimen__label">--rule-heavy · masthead only</div>
          <div style={{ borderTop: 'var(--rule-heavy)' }} />
        </div>
      </section>

      <section className="band">
        <SectionRule label="Components" />
        <div className="specimen">
          <div className="specimen__label">Badges — partner disclosure is a product requirement</div>
          <div style={{ display: 'flex', gap: 'var(--space-2xs)' }}>
            <PartnerBadge />
            <Badge tone="live">Live</Badge>
            <Badge>Fine dining</Badge>
          </div>
        </div>
        <div className="specimen">
          <div className="specimen__label">Byline</div>
          <Byline author="NOW! Editorial" date="7 September 2026" minutes={6} />
        </div>
        <div className="specimen">
          <div className="specimen__label">Story card — standard · portrait · horizontal · index</div>
          <div className="grid grid--3" style={{ marginTop: 'var(--space-s)' }}>
            <StoryCard article={articles[0]} locale={site.locale} timeZone={site.timezone} />
            <StoryCard article={articles[1]} variant="portrait" locale={site.locale} timeZone={site.timezone} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-m)' }}>
              <StoryCard
                article={articles[2]}
                variant="horizontal"
                locale={site.locale}
                timeZone={site.timezone}
              />
              <StoryCard
                article={articles[0]}
                variant="index"
                index={1}
                showDek={false}
                locale={site.locale}
                timeZone={site.timezone}
              />
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
