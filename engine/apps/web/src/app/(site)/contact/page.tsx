import type { Metadata } from 'next'
import Link from 'next/link'

import { BandHead } from '@/components/primitives'
import { getSiteConfig } from '@/lib/site'

/**
 * Contact.
 *
 * Details come from the site config row, and they are the REAL published
 * details of each city's office — not invented, and not a placeholder that
 * looks real enough to ship. Each block renders only if that field exists:
 * the Bali office publishes no email address, so Bali shows none rather than
 * a plausible guess a reader would write to and never hear back from.
 *
 * There is no contact form because there is no endpoint behind one. A form
 * that silently discards what someone typed is worse than an address.
 */

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteConfig()
  return { title: 'Contact', description: `How to reach ${site.name}.` }
}

export default async function ContactPage() {
  const site = await getSiteConfig()
  const c = site.contact ?? {}

  return (
    <div className="shell">
      <header className="band">
        <p className="kicker kicker--red">Contact</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          Get in touch
        </h1>
        <p className="dek" style={{ marginTop: 'var(--space-m)', maxWidth: '46ch' }}>
          Story tips, corrections, and anything we have got wrong — all of it is welcome.
        </p>
      </header>

      <section className="band" style={{ paddingTop: 0 }}>
        <div className="split">
          <div>
            <BandHead title="The office" />
            <div className="place-facts">
              {c.address?.length ? (
                <div className="place-facts__row">
                  <span className="place-facts__key">Address</span>
                  <span className="place-facts__val">
                    {c.address.map((line) => (
                      <span key={line} style={{ display: 'block' }}>
                        {line}
                      </span>
                    ))}
                  </span>
                </div>
              ) : null}

              {c.phone?.length ? (
                <div className="place-facts__row">
                  <span className="place-facts__key">Telephone</span>
                  <span className="place-facts__val">
                    {c.phone.map((number) => (
                      <a
                        key={number}
                        href={`tel:${number.replace(/[^+0-9]/g, '')}`}
                        style={{ display: 'block' }}
                      >
                        {number}
                      </a>
                    ))}
                  </span>
                </div>
              ) : null}

              {c.editorial ? (
                <div className="place-facts__row">
                  <span className="place-facts__key">Editorial</span>
                  <span className="place-facts__val">
                    <a href={`mailto:${c.editorial}`} style={{ borderBottom: '1px solid var(--red)' }}>
                      {c.editorial}
                    </a>
                  </span>
                </div>
              ) : null}

              {c.sales ? (
                <div className="place-facts__row">
                  <span className="place-facts__key">Advertising</span>
                  <span className="place-facts__val">
                    <a href={`mailto:${c.sales}`} style={{ borderBottom: '1px solid var(--red)' }}>
                      {c.sales}
                    </a>
                  </span>
                </div>
              ) : null}

              <div className="place-facts__row">
                <span className="place-facts__key">Hours</span>
                <span className="place-facts__val">Monday to Friday, {site.timezone.split('/')[1]?.replace('_', ' ')} time</span>
              </div>
            </div>
          </div>

          <div>
            <BandHead title="What to send where" />
            <div className="prose">
              <p>
                <strong>A correction.</strong> Tell us what is wrong and where you saw it. Prices,
                opening hours and addresses change constantly and we would rather hear it from you
                than leave it standing.
              </p>
              <p>
                <strong>A story tip.</strong> Something opening, closing, or worth a look. We read
                everything, though we cannot reply to all of it.
              </p>
              <p>
                <strong>Working with us.</strong> Partnerships, events and campaigns are on{' '}
                <Link href="/advertise" style={{ borderBottom: '1px solid var(--red)' }}>
                  Advertise
                </Link>
                .
              </p>
              <p>
                <strong>Writing for us.</strong> Send a short note and two things you have
                published. We commission from people who know the place first-hand.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
