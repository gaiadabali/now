import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect, notFound } from 'next/navigation'

import { AccountShell, Field, Submit, type StatusMessage } from '@/components/account'
import { currentReader, accountsEnabled } from '@/lib/reader'
import { signIn } from '@/lib/readerActions'

export const metadata: Metadata = {
  title: 'Sign in',
  robots: { index: false, follow: false },
}

function statusFor(status?: string): StatusMessage | undefined {
  switch (status) {
    // One message for both "no such address" and "wrong password". Anything
    // more specific turns this form into an address-validation service for
    // whoever is testing a breach list against it.
    case 'invalid':
      return {
        tone: 'bad',
        head: 'That did not work.',
        body: 'Check the address and password and try again.',
      }
    // Distinguishable on purpose: only reachable after a correct
    // identification, so it reveals nothing, and the legitimate owner would
    // otherwise keep retrying a password that is in fact correct.
    case 'locked':
      return {
        tone: 'bad',
        head: 'Too many attempts.',
        body: 'This account is locked for a few minutes. Try again shortly, or reset your password.',
      }
    case 'suspended':
      return {
        tone: 'bad',
        head: 'This account is suspended.',
        body: 'Get in touch and we will sort it out.',
      }
    case 'slow_down':
      return {
        tone: 'bad',
        head: 'Too many attempts.',
        body: 'Wait a few minutes before trying again.',
      }
    case 'signed_out':
      return { tone: 'ok', head: 'Signed out.', body: 'See you next time.' }
    default:
      return undefined
  }
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}) {
  // The whole surface is unreachable when mail is not configured — a form that
  // cannot complete is worse than no form (F141). notFound(), not a message:
  // an explanation would invite people to keep trying.
  if (!accountsEnabled()) notFound()
  if (await currentReader()) redirect('/account')

  const query = (await searchParams) ?? {}
  const status = statusFor(typeof query.status === 'string' ? query.status : undefined)

  return (
    <AccountShell
      kicker="Your account"
      title="Welcome back."
      status={status}
      footer={
        <>
          No account yet? <Link href="/account/register">Create one</Link>. Forgotten your password?{' '}
          <Link href="/account/forgot">Reset it</Link>.
        </>
      }
    >
      <form action={signIn}>
        <Field id="email" name="email" label="Email" type="email" autoComplete="email" required />
        <Field
          id="password"
          name="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          required
        />
        <Submit>Sign in</Submit>
      </form>
    </AccountShell>
  )
}
