import Link from 'next/link'
import { notFound } from 'next/navigation'

import { requireReviewerAccess } from '@/lib/auth'
import {
  areaOptions,
  deskMentions,
  deskPlace,
  duplicateCandidates,
  loadQueue,
  MENTION_LIMIT,
  subtypeOptions,
  verdictsFor,
} from '@/lib/placeDesk'
import { approvalCheck, type AliasEntry } from '@/lib/placeDeskRules'
import { getSiteConfig } from '@/lib/site'

import { AreaForm, DecisionButtons, MergeButtons, MergeByNumber, TypeForm } from './Decisions'
import { DESK_ROOT, placeHref } from './paths'

/**
 * One place, with the evidence an editor needs to decide it in about two
 * minutes (plan §9.1): which stories named it and how, what the resolver
 * knows about where it is (a map pin when it has coordinates), what the
 * junk rules and the region check say, and the places it might duplicate.
 * The decisions sit beside the evidence, not below it.
 */

const STATUS_LABEL: Record<string, string> = {
  pending_review: 'Waiting',
  active: 'Approved and live',
  junk: 'Junk',
  closed: 'Closed',
}

const dateFmt = (d: Date | string | null, timeZone: string) =>
  d ? new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone }).format(new Date(d)) : '—'

function MapPin({ lat, lng, name }: { lat: number; lng: number; name: string }) {
  // OpenStreetMap's own embed: no key, no dependency, its attribution
  // included. Never a Google map (plan §9.4).
  const d = 0.004
  const bbox = [lng - d, lat - d, lng + d, lat + d].map((n) => n.toFixed(5)).join('%2C')
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat.toFixed(6)}%2C${lng.toFixed(6)}`
  return (
    <figure className="place-desk__map">
      <iframe title={`Map: ${name}`} src={src} loading="lazy" referrerPolicy="no-referrer" />
      <figcaption>
        <a href={`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=18/${lat}/${lng}`} target="_blank" rel="noreferrer">
          Open in OpenStreetMap
        </a>{' '}
        · © OpenStreetMap contributors
      </figcaption>
    </figure>
  )
}

export async function PlaceDeskPlaceView({ id }: { id: string }) {
  await requireReviewerAccess()
  const placeId = Number(id)
  if (!Number.isInteger(placeId)) notFound()
  const site = await getSiteConfig()
  const place = await deskPlace(placeId)
  if (!place) notFound()

  const siteWords = [site.slug, ...site.name.split(/\s+/)].map((w) => w.replace(/[^a-z0-9]/gi, '')).filter(Boolean)
  const [mentions, duplicates, groups, areas, verdicts, queue] = await Promise.all([
    deskMentions(place.id),
    duplicateCandidates(place, siteWords),
    subtypeOptions(),
    areaOptions(site.slug),
    verdictsFor(place.name, site.slug),
    loadQueue(site.slug),
  ])
  const queued = queue.rows.find((r) => r.id === place.id)
  const approve = approvalCheck(place)
  const aliasEntries = Array.isArray(place.aliases) ? (place.aliases as Array<AliasEntry | string>) : []
  const tz = site.timezone
  const hasCoords = place.lat !== null && place.lng !== null

  return (
    <>
      <p className="classify__crumb">
        <Link href={DESK_ROOT}>← Place desk</Link>
      </p>
      <h1>{place.name}</h1>
      <p className="place-desk__status">
        <span className={`place-desk__state place-desk__state--${place.status}`}>{STATUS_LABEL[place.status] ?? place.status}</span>
        {queued?.rank ? <span className="classify__muted">No. {queued.rank} in the queue · score {queued.score.toFixed(1)}</span> : null}
        <span className="classify__muted">Place {place.id}</span>
        {place.status === 'active' ? (
          <Link href={`/places/${place.slug}`} target="_blank">
            View the live page
          </Link>
        ) : null}
      </p>

      {place.mergedInto ? (
        <p className="classify__note classify__note--flag">
          Merged into <Link href={placeHref(place.mergedInto)}>{place.mergedIntoName}</Link>. Its stories now belong to that
          place; decide that one instead.
        </p>
      ) : null}
      {verdicts.junk.tier === 'junk' ? (
        <p className="classify__note classify__note--flag">Looks like junk: {verdicts.junk.reason}.</p>
      ) : verdicts.junk.tier === 'suspect' ? (
        <p className="classify__note">Needs a look: {verdicts.junk.reason}.</p>
      ) : null}
      {verdicts.region.outOfRegion ? (
        <p className="classify__note">
          The name points at {verdicts.region.matched}, outside this city. Keep it if stories here mention it; it will
          not be suggested for itineraries in this city.
        </p>
      ) : null}

      <div className="place-desk__layout">
        <section className="place-desk__evidence" aria-labelledby="evidence-h">
          <h2 id="evidence-h" className="classify__subhead">
            The evidence
          </h2>
          <div className="classify__cards classify__cards--tight">
            <div className="classify__card">
              <div className="classify__n">{place.featured}</div>
              <div className="classify__k">Times featured</div>
            </div>
            <div className="classify__card">
              <div className="classify__n">{place.articles}</div>
              <div className="classify__k">Stories</div>
            </div>
            <div className="classify__card">
              <div className="classify__n">{place.newest ? new Date(place.newest).getFullYear() : '—'}</div>
              <div className="classify__k">Latest story</div>
            </div>
          </div>

          {mentions.length ? (
            <table>
              <caption className="classify__caption">
                {place.mentions > MENTION_LIMIT
                  ? `The ${MENTION_LIMIT} most telling of ${place.mentions} mentions, featured first.`
                  : 'Every story that names it, featured first.'}
              </caption>
              <thead>
                <tr>
                  <th scope="col">Story</th>
                  <th scope="col">How</th>
                  <th scope="col">What the story called it</th>
                  <th scope="col">Published</th>
                </tr>
              </thead>
              <tbody>
                {mentions.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <Link href={`/team-editor/collections/articles/${m.articleId}`}>{m.title}</Link>
                    </td>
                    <td>
                      <span className={`classify__pill${m.role === 'featured' ? ' place-desk__pill--featured' : ''}`}>
                        {m.role === 'featured' ? 'Featured' : 'Mentioned'}
                      </span>
                    </td>
                    <td className="classify__muted">{m.surface}</td>
                    <td className="classify__muted">{dateFmt(m.publishedAt, tz)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="classify__empty">No story names this place.</p>
          )}

          <h2 className="classify__subhead">Where it is</h2>
          <dl className="place-desk__facts">
            <dt>Address</dt>
            <dd>{place.address ?? 'Not known'}</dd>
            <dt>Area</dt>
            <dd>{place.area ?? 'Not set'}</dd>
            <dt>Coordinates</dt>
            <dd>
              {hasCoords ? `${place.lat!.toFixed(5)}, ${place.lng!.toFixed(5)}` : 'None yet'}
              {place.geoSource ? ` · from ${place.geoSource}` : ''}
              {place.geoConfidence !== null ? ` · confidence ${Math.round(place.geoConfidence * 100)}%` : ''}
            </dd>
            <dt>Resolver</dt>
            <dd>
              {place.googlePlaceId || place.businessStatus || place.geoSource
                ? [
                    place.geoSource ? `coordinates from ${place.geoSource}` : null,
                    place.googlePlaceId ? `Google place id ${place.googlePlaceId}` : null,
                    place.businessStatus ? `status ${place.businessStatus.replace(/_/g, ' ')}` : null,
                  ]
                    .filter(Boolean)
                    .join(' · ')
                : 'Not looked up yet. The open-data lookup (plan P1.3) has not run for this place.'}
            </dd>
            <dt>In this city?</dt>
            <dd>
              {place.regionOk
                ? 'Yes, its coordinates are inside the region.'
                : verdicts.region.outOfRegion
                  ? `The name says ${verdicts.region.matched}.`
                  : hasCoords
                    ? 'Not checked yet: the region test runs with the open-data lookup (plan P1.3).'
                    : 'Not confirmed until it has coordinates.'}
            </dd>
          </dl>
          {hasCoords ? <MapPin lat={place.lat!} lng={place.lng!} name={place.name} /> : null}

          {aliasEntries.length ? (
            <>
              <h2 className="classify__subhead">Other names it has been called</h2>
              <ul className="place-desk__aliases">
                {aliasEntries.map((a, i) =>
                  typeof a === 'string' ? (
                    <li key={i}>{a}</li>
                  ) : (
                    <li key={i}>
                      <strong>{a.name}</strong>{' '}
                      <span className="classify__muted">
                        merged in {dateFmt(a.mergedAt, tz)} · {a.mentionIds?.length ?? 0} mention
                        {(a.mentionIds?.length ?? 0) === 1 ? '' : 's'} moved
                        {a.inheritedAliases?.length ? ` · also known as ${a.inheritedAliases.join(', ')}` : ''}
                      </span>
                    </li>
                  ),
                )}
              </ul>
            </>
          ) : null}
        </section>

        <aside className="place-desk__decisions" aria-labelledby="decide-h">
          <h2 id="decide-h" className="classify__subhead">
            Your decision
          </h2>
          {place.mergedInto ? (
            <p className="classify__muted">Nothing to decide here: it was merged.</p>
          ) : (
            <>
              <div className="place-desk__step">
                <h3>Is it a real place?</h3>
                <DecisionButtons id={place.id} status={place.status} approveBlockedBecause={approve.ok ? null : approve.why} />
              </div>
              <div className="place-desk__step">
                <h3>What kind of place is it?</h3>
                <p className="place-desk__hint">
                  Now: {place.type && !['editorial', 'unknown'].includes(place.type) ? `${place.subtype} (${place.type})` : 'not set'}.
                  Keeps a rival hotel or restaurant off its stories&rsquo; pages.
                </p>
                <TypeForm id={place.id} groups={groups} current={place.subtype} />
              </div>
              <div className="place-desk__step">
                <h3>Which area?</h3>
                <AreaForm id={place.id} home={areas.home} elsewhere={areas.elsewhere} current={place.area} homeLabel={site.name} />
              </div>
              <div className="place-desk__step">
                <h3>Is it the same place as one of these?</h3>
                {duplicates.length ? (
                  <ul className="place-desk__dupes">
                    {duplicates.map((d) => (
                      <li key={d.id}>
                        <Link href={placeHref(d.id)}>{d.name}</Link>{' '}
                        <span className="classify__muted">
                          {d.featured} featured · {d.articles} stories{d.status === 'active' ? ' · live' : ''} · place {d.id}
                        </span>
                        <MergeButtons id={place.id} other={d.id} otherName={d.name} />
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="classify__muted">No likely duplicates by name.</p>
                )}
                <MergeByNumber id={place.id} />
              </div>
              <p className="place-desk__hint">
                {place.reviewedByEmail
                  ? `Last decided by ${place.reviewedByEmail}${place.verifiedAt ? `, approved ${dateFmt(place.verifiedAt, tz)}` : ''}.`
                  : 'No one has decided this place yet.'}{' '}
                Every decision is saved as a version with your name on it.
              </p>
            </>
          )}
        </aside>
      </div>
    </>
  )
}
