import type { Metadata } from 'next'
import Link from 'next/link'

import { SectionRule } from '@/components/primitives'
import { getSiteConfig } from '@/lib/site'

/**
 * Podcast.
 *
 * Renders the city's real show when it has one and says so plainly when it
 * does not. Bali publishes a show; Jakarta does not, and a shared "coming
 * soon" on both was wrong in one direction and uninformative in the other.
 *
 * The episode list is Spotify's own embed rather than a feed we parse: it is
 * always current, it plays in place, and it means no episode metadata to keep
 * in sync with a platform that already has it.
 */

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteConfig()
  return {
    title: 'Podcast',
    description: site.podcast ? site.podcast.name : `The ${site.name} podcast.`,
  }
}

export default async function PodcastPage() {
  const site = await getSiteConfig()
  const show = site.podcast

  return (
    <div className="shell">
      <header className="band">
        <p className="kicker kicker--red">Podcast</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          {show ? show.name : 'Not yet'}
        </h1>
        <p className="dek" style={{ marginTop: 'var(--space-m)', maxWidth: '48ch' }}>
          {show
            ? 'Conversations with the people behind the places we write about — chefs, hoteliers, artists and the occasional troublemaker.'
            : `${site.name} does not publish a podcast today. When there is a show, it will be here — and we would rather say nothing than advertise something that does not exist.`}
        </p>
      </header>

      {show ? (
        <>
          <section className="band" style={{ paddingTop: 0 }}>
            <iframe
              title={show.name}
              src={`https://open.spotify.com/embed/show/${show.spotifyShowId}?theme=0`}
              width="100%"
              height="420"
              style={{ border: 0, borderRadius: '4px' }}
              loading="lazy"
              allow="clipboard-write; encrypted-media; fullscreen; picture-in-picture"
            />
            <p className="meta" style={{ marginTop: 'var(--space-xs)' }}>
              <a
                href={show.url}
                target="_blank"
                rel="noreferrer noopener"
                style={{ borderBottom: '1px solid var(--red)' }}
              >
                Open in Spotify →
              </a>
            </p>
          </section>

          <section className="band" style={{ paddingTop: 0 }}>
            <SectionRule label="Also worth your time" />
            <p className="dek" style={{ maxWidth: '52ch' }}>
              If you would rather read than listen, the same reporting is in{' '}
              <Link href="/guides" style={{ borderBottom: '1px solid var(--red)' }}>
                the guides
              </Link>
              , and the weekly edit arrives by email if you{' '}
              <Link href="/subscribe" style={{ borderBottom: '1px solid var(--red)' }}>
                subscribe
              </Link>
              .
            </p>
          </section>
        </>
      ) : (
        <section className="band" style={{ paddingTop: 0 }}>
          <p className="dek" style={{ maxWidth: '52ch' }}>
            In the meantime, the weekly edit arrives by email —{' '}
            <Link href="/subscribe" style={{ borderBottom: '1px solid var(--red)' }}>
              subscribe here
            </Link>
            .
          </p>
        </section>
      )}
    </div>
  )
}
