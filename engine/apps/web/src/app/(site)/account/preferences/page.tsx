import type { Metadata } from 'next'
import { redirect } from 'next/navigation'

import { AccountShell, Submit, type StatusMessage } from '@/components/account'
import { ChipGroup } from '@/components/chips'
import { currentReader } from '@/lib/reader'
import { savePreferences } from '@/lib/readerActions'
import { hasChosen, loadPrefs, loadVocabulary } from '@/lib/preferences'

export const metadata: Metadata = {
  title: 'What you are into',
  robots: { index: false, follow: false },
}

export const dynamic = 'force-dynamic'

/**
 * ARCHITECTURE §17's registration flow (E8.4).
 *
 * **One page, not a wizard.** §17 budgets the whole thing at 30 seconds, and
 * four screens with a Next button between them cannot be done in 30 seconds by
 * anyone. Everything is visible, nothing is required, and the form submits
 * without JavaScript.
 *
 * The same page is the edit surface. §17 asks for the picks to be shown back
 * and corrected — *"corrections are high-quality training signal"* — so
 * there is no separate read-only view to keep in sync.
 */
export default async function PreferencesPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}) {
  const reader = await currentReader()
  if (!reader) redirect('/account/login')

  const query = (await searchParams) ?? {}
  const status: StatusMessage | undefined =
    query.status === 'verified'
      ? {
          tone: 'ok',
          head: 'Your email is confirmed.',
          body: 'You are signed in. One more thing and the site starts adjusting to you.',
        }
      : undefined

  const [vocabulary, prefs] = await Promise.all([loadVocabulary(), loadPrefs(reader.id)])
  const returning = hasChosen(prefs)

  return (
    <AccountShell
      kicker="Your account"
      title={returning ? 'What you are into.' : 'Tell us what you are into.'}
      status={status}
      dek={
        returning
          ? 'Change any of it. What you actually read counts too, and counts more the longer you read — this is the starting point, not the whole picture.'
          : 'Pick a few things. It takes about twenty seconds and the site starts adjusting immediately. Nothing here is permanent.'
      }
    >
      <form action={savePreferences}>
        <ChipGroup
          name="interests"
          legend="What are you into?"
          hint="The broad strokes. Pick three or more."
          options={vocabulary.interests}
          selected={prefs.interests}
        />
        <ChipGroup
          name="topics"
          legend="Anything more specific?"
          hint="Optional, and the part that makes recommendations feel less generic."
          options={vocabulary.topics}
          selected={prefs.topics}
        />
        <ChipGroup
          name="areas"
          legend="Where do you spend time?"
          hint="One to three neighbourhoods."
          options={vocabulary.areas}
          selected={prefs.areas}
        />
        <ChipGroup
          name="persona"
          legend="You're…"
          options={vocabulary.personas}
          selected={prefs.persona ? [prefs.persona] : []}
          single
          allowNone
        />
        <ChipGroup
          name="budget"
          legend="Budget"
          hint="Skippable — it filters nothing out, it just orders things."
          options={vocabulary.budgets}
          selected={prefs.budget ? [prefs.budget] : []}
          single
          allowNone
        />
        <Submit>{returning ? 'Save changes' : 'Save and start reading'}</Submit>
      </form>
    </AccountShell>
  )
}
