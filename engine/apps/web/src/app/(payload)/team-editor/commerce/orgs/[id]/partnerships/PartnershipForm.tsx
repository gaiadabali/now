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
 * The one client component in this area not styled from scratch: every
 * class name below already exists in `styles/admin.css` from S5.1
 * (`platform__form`, `platform__field`, `platform__btn`, `platform__notice`)
 * except the handful under the `WS4 platform` block this ticket adds for
 * the confirm panel and the tier/status pills.
 */

export type SiteOption = { id: string; slug: string; name: string }

const TIERS: PartnershipTier[] = ['free', 'listed', 'paid']
const STATUSES: PartnershipStatus[] = ['active', 'paused', 'ended']

function toDateInput(value: string | null): string {
  if (!value) return ''
  // `<input type="date">` wants YYYY-MM-DD; the server gives an ISO timestamp.
  return value.slice(0, 10)
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
      linkPolicyJson: Object.keys(existing.linkPolicy ?? {}).length ? JSON.stringify(existing.linkPolicy) : '',
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
    linkPolicyJson: '',
    customUrl: '',
    utmTemplate: '',
    showBadge: false,
    badgeLabel: '',
    itineraryEligible: false,
    boostCap: '',
  }
}

type Phase = { kind: 'editing' } | { kind: 'confirming'; blastRadius: import('@/lib/queries').BlastRadius }

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
          <p className="ws4-blast__figure">
            {phase.blastRadius.computable
              ? `${phase.blastRadius.articleCount.toLocaleString()} article(s) across ${phase.blastRadius.venueCount.toLocaleString()} venue(s)`
              : 'Blast radius unavailable from this admin session'}
          </p>
          <p className="platform__sub">{phase.blastRadius.note}</p>
          <div className="platform__row-actions">
            <button className="platform__btn" onClick={onCancelConfirm} type="button">
              Cancel — keep editing
            </button>
            <button className="platform__btn platform__btn--primary" disabled={pending} onClick={onConfirm} type="button">
              {pending ? 'Saving…' : 'Confirm and save'}
            </button>
          </div>
        </div>
      ) : (
        <form className="platform__form" onSubmit={onReview}>
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
            </label>

            <label className="platform__field">
              <span className="platform__field-label">Contract starts</span>
              <input onChange={(e) => set('startsAt', e.target.value)} type="date" value={values.startsAt} />
            </label>

            <label className="platform__field">
              <span className="platform__field-label">Contract ends</span>
              <input onChange={(e) => set('endsAt', e.target.value)} type="date" value={values.endsAt} />
            </label>

            <label className="platform__field">
              <span className="platform__field-label">Custom URL</span>
              <input
                onChange={(e) => set('customUrl', e.target.value)}
                placeholder="https://partner.example/offer?utm=now"
                type="text"
                value={values.customUrl}
              />
            </label>

            <label className="platform__field">
              <span className="platform__field-label">UTM template</span>
              <input onChange={(e) => set('utmTemplate', e.target.value)} type="text" value={values.utmTemplate} />
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
            </label>

            <label className="platform__field">
              <span className="platform__field-label">Boost cap (0–1)</span>
              <input onChange={(e) => set('boostCap', e.target.value)} placeholder="0.20" type="text" value={values.boostCap} />
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
              Eligible for guaranteed itinerary slots
            </label>
          </div>

          <label className="platform__field">
            <span className="platform__field-label">Link policy (JSON, optional)</span>
            <textarea
              onChange={(e) => set('linkPolicyJson', e.target.value)}
              placeholder="{}"
              rows={2}
              value={values.linkPolicyJson}
            />
          </label>
          <p className="platform__sub">
            Captured for the record; <code>now_link_resolver</code> does not read this field yet — it decides{' '}
            <code>rel=&quot;sponsored&quot;</code> and the badge from tier and the fields above.
          </p>

          <div className="platform__row-actions">
            <button className="platform__btn platform__btn--primary" disabled={pending} type="submit">
              {pending ? 'Checking…' : 'Save'}
            </button>
          </div>
        </form>
      )}
    </>
  )
}
