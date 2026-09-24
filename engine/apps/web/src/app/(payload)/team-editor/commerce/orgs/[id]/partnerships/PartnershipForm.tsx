'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'

import type { PartnershipDetail, PartnershipStatus, PartnershipTier } from '@/lib/queries'

import { createPartnershipAction, previewPartnershipSave, updatePartnershipAction } from './actions'
import type { PartnershipFormValues } from './actions'
import { partnershipHref } from '../../../paths'

/**
 * S5.2's write form and S5.3's blast-radius gate, together — they are one
 * interaction, not two screens, because the whole point of S5.3 is that a
 * commit cannot happen without having seen it first.
 *
 * **Three phases, not two.** `editing` → `previewPartnershipSave` →
 * `confirming` → the real write action → `editing` again (now showing
 * whatever was actually saved). There is no path from `editing` to a write
 * that skips `confirming`: the submit handler on the form always calls the
 * preview action, never the save action directly, so "dismissible only by
 * confirming" (docs/SURFACES-PLAN.md S5.3) is a property of which function
 * the button is wired to, not a rule enforced by hiding a button.
 *
 * Every label and hint here is written for the person filling it in, not for
 * whoever reads the schema — no table name, no package name, no HTTP header
 * value. What each tier and status DOES on the site is ARCHITECTURE.md §11's
 * own tier ladder, restated in plain words rather than cited.
 */

export type SiteOption = { id: string; slug: string; name: string; locale: string }

const TIERS: PartnershipTier[] = ['free', 'listed', 'paid']
const STATUSES: PartnershipStatus[] = ['active', 'paused', 'ended']

const TIER_HINTS: Record<PartnershipTier, string> = {
  free: 'Shown as plain text. No link, no badge, nothing for a reader to click.',
  listed: "Mentions link to the venue's own page on this site. No paid styling, no badge.",
  paid: 'Mentions link out to the URL below, marked as a paid placement and eligible for boosted placement in suggestions.',
}

const STATUS_HINTS: Record<PartnershipStatus, string> = {
  active: 'Live now, within the contract dates below.',
  paused: 'Off for now. The site treats every mention as if there were no partnership at all.',
  ended: 'Contract over. Same effect as paused — nothing links or shows a badge.',
}

function toDateInput(value: string | null): string {
  if (!value) return ''
  // `<input type="date">` wants YYYY-MM-DD; the server gives an ISO timestamp.
  return value.slice(0, 10)
}

/**
 * `<input type="date">`'s own placeholder/format is the BROWSER's locale,
 * not this page's `lang` attribute — verified empirically, not assumed: the
 * `lang` attribute below is set correctly and the widget still shows
 * `mm/dd/yyyy` regardless, because that is a browser (OS) setting a page
 * cannot reach. So the site's actual locale format is shown here instead, in
 * a plain line under the field, computed from the value the user just
 * picked — the one thing that IS reliably under this page's control.
 */
function formatDateForLocale(isoDate: string, locale: string | undefined): string {
  if (!isoDate) return 'No date set'
  const parsed = new Date(`${isoDate}T00:00:00Z`)
  if (Number.isNaN(parsed.getTime())) return ''
  try {
    return new Intl.DateTimeFormat(locale || 'en', { dateStyle: 'long', timeZone: 'UTC' }).format(parsed)
  } catch {
    return isoDate
  }
}

function initialValues(orgId: string, sites: SiteOption[], existing: PartnershipDetail | null): PartnershipFormValues {
  if (existing) {
    return {
      orgId: existing.orgId,
      placeId: existing.placeId,
      siteSlug: existing.siteSlug,
      siteId: existing.siteId,
      tier: existing.tier,
      status: existing.status,
      startsAt: toDateInput(existing.startsAt),
      endsAt: toDateInput(existing.endsAt),
      customUrl: existing.customUrl ?? '',
      utmTemplate: existing.utmTemplate ?? '',
      showBadge: existing.showBadge,
      badgeLabel: existing.badgeLabel ?? '',
      itineraryEligible: existing.itineraryEligible,
      boostCap: existing.boostCap === null ? '' : String(existing.boostCap),
    }
  }
  const first = sites[0]
  return {
    orgId,
    placeId: null,
    siteSlug: first?.slug ?? '',
    siteId: first?.id ?? '',
    tier: 'free',
    status: 'active',
    startsAt: '',
    endsAt: '',
    customUrl: '',
    utmTemplate: '',
    showBadge: false,
    badgeLabel: '',
    itineraryEligible: false,
    boostCap: '',
  }
}

type Phase = { kind: 'editing' } | { kind: 'confirming'; blastRadius: import('@/lib/queries').BlastRadius }

function plural(n: number, one: string, many: string): string {
  return `${n.toLocaleString()} ${n === 1 ? one : many}`
}

/** The headline figure on the confirm screen — always grammatical, whatever the count. */
function blastHeadline(b: import('@/lib/queries').BlastRadius): string {
  if (!b.computable) return 'Cannot check from here'
  if (b.linkedVenueCount === 0) return 'No venue linked yet'
  return `${plural(b.articleCount, 'article', 'articles')} across ${plural(b.venueCount, 'venue', 'venues')}`
}

export function PartnershipForm({
  orgId,
  orgName,
  sites,
  existing,
}: {
  orgId: string
  orgName: string
  sites: SiteOption[]
  existing: PartnershipDetail | null
}) {
  const router = useRouter()
  const [values, setValues] = useState<PartnershipFormValues>(() => initialValues(orgId, sites, existing))
  const [phase, setPhase] = useState<Phase>({ kind: 'editing' })
  const [notice, setNotice] = useState<{ ok: boolean; message: string } | null>(null)
  const [pending, startTransition] = useTransition()

  const isEdit = Boolean(existing)
  const selectedSite = sites.find((s) => s.slug === values.siteSlug) ?? sites[0]

  function set<K extends keyof PartnershipFormValues>(key: K, value: PartnershipFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }))
  }

  function onSiteChange(slug: string) {
    const site = sites.find((s) => s.slug === slug)
    setValues((prev) => ({ ...prev, siteSlug: slug, siteId: site?.id ?? '' }))
  }

  function onReview(event: React.FormEvent) {
    event.preventDefault()
    startTransition(async () => {
      const result = await previewPartnershipSave(values)
      if (!result.ok) {
        setNotice({ ok: false, message: result.message })
        return
      }
      setNotice(null)
      setPhase({ kind: 'confirming', blastRadius: result.blastRadius })
    })
  }

  function onConfirm() {
    startTransition(async () => {
      const result = isEdit && existing
        ? await updatePartnershipAction(existing.id, values)
        : await createPartnershipAction(values)
      setPhase({ kind: 'editing' })
      if (!result.ok) {
        setNotice({ ok: false, message: result.message })
        return
      }
      setNotice({ ok: true, message: result.message })
      if (!isEdit) {
        router.push(partnershipHref(orgId, result.partnership.id))
      }
    })
  }

  function onCancelConfirm() {
    setPhase({ kind: 'editing' })
  }

  return (
    <>
      {notice ? (
        <div aria-live="polite" className={`platform__notice ${notice.ok ? 'platform__notice--ok' : 'platform__notice--bad'}`}>
          <p>{notice.message}</p>
          <button className="platform__btn" onClick={() => setNotice(null)} type="button">
            Dismiss
          </button>
        </div>
      ) : null}

      {phase.kind === 'confirming' ? (
        <div className="ws4-blast" role="alertdialog" aria-label="Confirm this change">
          <h3>Before this saves</h3>
          <p className="ws4-blast__figure">{blastHeadline(phase.blastRadius)}</p>
          <p className="platform__sub">{phase.blastRadius.note}</p>
          {phase.blastRadius.linkedVenueCount === 0 ? (
            <p className="platform__sub">
              <a href="#venues">Link a venue to this organisation ↓</a>
            </p>
          ) : null}
          {phase.blastRadius.orgArticleLinkCount ? (
            <p className="platform__sub">
              Separately: {plural(phase.blastRadius.orgArticleLinkCount, 'article already links', 'articles already link')} to this
              organisation&rsquo;s own website — real exposure today, whether or not a venue is linked here.
            </p>
          ) : null}
          <div className="platform__row-actions">
            <button className="platform__btn" onClick={onCancelConfirm} type="button">
              Cancel — keep editing
            </button>
            <button className="platform__btn ws4-btn--primary" disabled={pending} onClick={onConfirm} type="button">
              {pending ? 'Saving…' : 'Confirm and save'}
            </button>
          </div>
        </div>
      ) : (
        <form className="platform__form ws4-partnership-form" onSubmit={onReview}>
          <div className="platform__fields">
            <label className="platform__field">
              <span className="platform__field-label">Organisation</span>
              <input disabled type="text" value={orgName} />
            </label>

            <label className="platform__field">
              <span className="platform__field-label">Site</span>
              <select
                disabled={isEdit}
                onChange={(e) => onSiteChange(e.target.value)}
                value={values.siteSlug}
              >
                {sites.map((s) => (
                  <option key={s.id} value={s.slug}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="platform__field">
              <span className="platform__field-label">Tier</span>
              <select onChange={(e) => set('tier', e.target.value as PartnershipTier)} value={values.tier}>
                {TIERS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <span className="ws4-hint">{TIER_HINTS[values.tier]}</span>
            </label>

            <label className="platform__field">
              <span className="platform__field-label">Status</span>
              <select onChange={(e) => set('status', e.target.value as PartnershipStatus)} value={values.status}>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <span className="ws4-hint">{STATUS_HINTS[values.status]}</span>
            </label>

            <label className="platform__field">
              <span className="platform__field-label">Contract starts</span>
              <input
                lang={selectedSite?.locale}
                onChange={(e) => set('startsAt', e.target.value)}
                type="date"
                value={values.startsAt}
              />
              <span className="ws4-hint">{formatDateForLocale(values.startsAt, selectedSite?.locale)}</span>
            </label>

            <label className="platform__field">
              <span className="platform__field-label">Contract ends</span>
              <input
                lang={selectedSite?.locale}
                onChange={(e) => set('endsAt', e.target.value)}
                type="date"
                value={values.endsAt}
              />
              <span className="ws4-hint">{formatDateForLocale(values.endsAt, selectedSite?.locale)}</span>
            </label>

            <label className="platform__field">
              <span className="platform__field-label">Custom URL</span>
              <input
                onChange={(e) => set('customUrl', e.target.value)}
                placeholder="https://partner.example/offer?utm=now"
                type="text"
                value={values.customUrl}
              />
              <span className="ws4-hint">Where a paid link sends a reader. Only used for the paid tier.</span>
            </label>

            <label className="platform__field">
              <span className="platform__field-label">UTM template</span>
              <input onChange={(e) => set('utmTemplate', e.target.value)} type="text" value={values.utmTemplate} />
              <span className="ws4-hint">Optional tracking tag added to that link, for this partner&rsquo;s own reporting.</span>
            </label>

            <label className="platform__field">
              <span className="platform__field-label">Badge label</span>
              <input
                disabled={!values.showBadge}
                onChange={(e) => set('badgeLabel', e.target.value)}
                placeholder="Partner"
                type="text"
                value={values.badgeLabel}
              />
              <span className="ws4-hint">The word shown on the badge next to a paid mention, e.g. &ldquo;Partner&rdquo;.</span>
            </label>

            <label className="platform__field">
              <span className="platform__field-label">Most this partner can be lifted in suggestions</span>
              <input onChange={(e) => set('boostCap', e.target.value)} placeholder="0.2" type="text" value={values.boostCap} />
              <span className="ws4-hint">
                0 to 1 — 0.2 means up to a 20% boost in ranked lists. Leave blank for no boost at all.
              </span>
            </label>
          </div>

          <div className="platform__row-actions ws4-checkboxes">
            <label>
              <input checked={values.showBadge} onChange={(e) => set('showBadge', e.target.checked)} type="checkbox" />
              Show a partner badge
            </label>
            <label>
              <input
                checked={values.itineraryEligible}
                onChange={(e) => set('itineraryEligible', e.target.checked)}
                type="checkbox"
              />
              Eligible for guaranteed slots in trip itineraries
            </label>
          </div>

          <div className="platform__row-actions">
            <button className="platform__btn ws4-btn--primary" disabled={pending} type="submit">
              {pending ? 'Checking…' : 'Save'}
            </button>
          </div>
        </form>
      )}
    </>
  )
}
