import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import Link from 'next/link'

import { AccountShell, Field, Submit, type StatusMessage } from '@/components/account'
import { resendVerification } from '@/lib/readerActions'
import { accountsEnabled } from '@/lib/reader'

export const metadata: Metadata = {
  title: 'Confirm your email',
  robots: { index: false, follow: false },
}

/**
 * The human-facing half of verification.
 *
 * It renders only. The token is consumed by the route handler at
 * `/account/verify/confirm`, which is where the emailed link points, because
 * signing someone in means setting a cookie and Next permits that from a route
 * handler or Server Action — not from a page render.
 */
export const dynamic = 'force-dynamic'

function statusFor(flag?: string): { status: StatusMessage; showResend: boolean } {
  switch (flag) {
    case 'invalid':
      return {
        // One message for expired, already-used and never-existed.
        status: {
          tone: 'bad',
          head: 'That link is no longer valid.',
          body: 'Confirmation links last 24 hours and work once. Enter your address and we will send a fresh one.',
        },
        showResend: true,
      }
    case 'resent':
      return {
        status: {
          tone: 'ok',
          head: 'On its way.',
          body: 'If that address still needs confirming, a new link is in your inbox.',
        },
        showResend: false,
      }
    case 'slow_down':
      return {
        status: {
          tone: 'bad',
          head: 'Too many requests.',
          body: 'Wait a little before asking for another link.',
        },
        showResend: true,
      }
    case 'unavailable':
      return {
        status: {
          tone: 'bad',
          head: 'Something went wrong at our end.',
          body: 'Your link may still be good — try it again in a moment.',
        },
        showResend: true,
      }
    default:
      return {
        status: {
          tone: 'info',
          head: 'Confirm your email.',
          body: 'Open the link we sent you. If it never arrived, ask for another below.',
        },
        showResend: true,
      }
  }
}

export default async function VerifyPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}) {
  // The whole surface is unreachable when mail is not configured — a form that
  // cannot complete is worse than no form (F141). notFound(), not a message:
  // an explanation would invite people to keep trying.
  if (!accountsEnabled()) notFound()
  const query = (await searchParams) ?? {}
  const { status, showResend } = statusFor(
    typeof query.status === 'string' ? query.status : undefined,
  )

  return (
    <AccountShell
      kicker="Your account"
      title="Confirming your address."
      status={status}
      footer={
        <>
          Already confirmed? <Link href="/account">Go to your account</Link>.
        </>
      }
    >
      {showResend ? (
        <form action={resendVerification}>
          <Field id="email" name="email" label="Email" type="email" autoComplete="email" required />
          <Submit>Send a new link</Submit>
        </form>
      ) : null}
    </AccountShell>
  )
}
