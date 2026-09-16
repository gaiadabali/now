import type { Metadata } from 'next'
import Link from 'next/link'

import { AccountShell, Field, Submit, type StatusMessage } from '@/components/account'
import { requestReset } from '@/lib/readerActions'

export const metadata: Metadata = {
  title: 'Reset your password',
  robots: { index: false, follow: false },
}

export default async function ForgotPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}) {
  const query = (await searchParams) ?? {}
  // One outcome, always. Whether the address has an account, whether it is
  // suspended, whether the request was rate-limited — all land here with the
  // same words. This page is the classic place an enumeration oracle is left
  // open by accident.
  const status: StatusMessage | undefined =
    query.status === 'sent'
      ? {
          tone: 'ok',
          head: 'Check your email.',
          body: 'If that address has an account, a reset link is on its way. It expires in an hour and works once.',
        }
      : undefined

  return (
    <AccountShell
      kicker="Your account"
      title="Forgotten your password?"
      dek="Give us the address you signed up with and we will send a link to set a new one."
      status={status}
      footer={
        <>
          Remembered it? <Link href="/account/login">Sign in</Link>.
        </>
      }
    >
      <form action={requestReset}>
        <Field id="email" name="email" label="Email" type="email" autoComplete="email" required />
        <Submit>Send reset link</Submit>
      </form>
    </AccountShell>
  )
}
