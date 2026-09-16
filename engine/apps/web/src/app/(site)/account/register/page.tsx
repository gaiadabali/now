import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { AccountShell, Field, Submit, type StatusMessage } from '@/components/account'
import { MIN_PASSWORD_LENGTH } from '@now/auth'
import { currentReader } from '@/lib/reader'
import { register } from '@/lib/readerActions'
import { getSiteConfig } from '@/lib/site'

export async function generateMetadata(): Promise<Metadata> {
  const site = await getSiteConfig()
  return {
    title: 'Create an account',
    description: `Save places, plan trips and get ${site.name} tuned to what you actually read.`,
    // Sign-up, sign-in and every token-bearing page stay out of the index.
    robots: { index: false, follow: false },
  }
}

const WEAK: Record<string, string> = {
  too_short: `Use at least ${MIN_PASSWORD_LENGTH} characters. Length matters far more than symbols.`,
  too_long: 'That is longer than we can accept — trim it a little.',
  too_common: 'That one appears in every breach list there is. Pick something less guessable.',
}

function statusFor(status?: string, why?: string): StatusMessage | undefined {
  switch (status) {
    // Says nothing about whether the address was new. An address that already
    // has an account reaches this exact page — see lib/readerActions.ts.
    case 'check_email':
      return {
        tone: 'ok',
        head: 'Check your email.',
        body: 'If we can set up an account for that address, a confirmation link is on its way. It expires in 24 hours.',
      }
    case 'invalid_email':
      return { tone: 'bad', head: 'That address did not look right.', body: 'Check it for a typo and try again.' }
    case 'weak_password':
      return {
        tone: 'bad',
        head: 'Pick a stronger password.',
        body: WEAK[why ?? 'too_short'] ?? (WEAK.too_short as string),
      }
    case 'slow_down':
      return {
        tone: 'bad',
        head: 'Too many attempts.',
        body: 'Wait a few minutes before trying that address again.',
      }
    // Reached only when sign-up is misconfigured at our end — it affects every
    // address equally, so saying so plainly reveals nothing about any of them.
    case 'unavailable':
      return {
        tone: 'bad',
        head: 'Sign-up is temporarily unavailable.',
        body: 'Nothing was created and nothing was lost. Please try again shortly.',
      }
    default:
      return undefined
  }
}

export default async function RegisterPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}) {
  if (await currentReader()) redirect('/account')

  const query = (await searchParams) ?? {}
  const status = statusFor(
    typeof query.status === 'string' ? query.status : undefined,
    typeof query.why === 'string' ? query.why : undefined,
  )

  return (
    <AccountShell
      kicker="Your account"
      title="Make the city yours."
      dek="Tell us what you are into and we will stop showing you the rest. Save places, keep your itineraries, and pick up where you left off."
      status={status}
      footer={
        <>
          Already have an account? <Link href="/account/login">Sign in</Link>.
        </>
      }
    >
      <form action={register}>
        <Field id="name" name="name" label="Name" autoComplete="name" hint="Optional — what we call you." />
        <Field id="email" name="email" label="Email" type="email" autoComplete="email" required />
        <Field
          id="password"
          name="password"
          label="Password"
          type="password"
          autoComplete="new-password"
          required
          minLength={MIN_PASSWORD_LENGTH}
          hint={`At least ${MIN_PASSWORD_LENGTH} characters. A phrase you can remember beats a short tangle of symbols.`}
        />
        <Submit>Create account</Submit>
      </form>
    </AccountShell>
  )
}
