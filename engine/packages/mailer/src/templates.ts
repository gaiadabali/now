/**
 * The three messages E8 needs to send.
 *
 * Each template returns `subject`, `text` and `html` from **one** set of
 * inputs, so the plain-text part cannot drift from the HTML one. Templates
 * kept in two files drift within a month, and the half that drifts is always
 * the text part, because nobody reads it.
 *
 * Deliberately plain HTML — a table-based responsive email framework is a lot
 * of surface for four sentences and a link. These render correctly in clients
 * that strip CSS entirely, which is the only compatibility that matters for a
 * message whose job is to carry one link.
 */

export type Rendered = {
  subject: string
  text: string
  html: string
}

export type Branding = {
  /** "NOW! Jakarta" — the masthead, from the site config. */
  siteName: string
  /** Where a reader replies or complains. Shown, not just set as a header. */
  supportEmail: string
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * The link is escaped like any other interpolation. It is ours — built by
 * `buildLink` from a configured origin — but "it is ours" is exactly what
 * stops being true the first time someone adds a `next=` parameter.
 */
function layout(branding: Branding, heading: string, body: string, action?: { label: string; url: string }): string {
  const button = action
    ? `<p style="margin:28px 0"><a href="${escapeHtml(action.url)}" style="background:#111;color:#fff;padding:12px 20px;border-radius:6px;text-decoration:none;display:inline-block">${escapeHtml(action.label)}</a></p>
       <p style="color:#666;font-size:13px;margin:0 0 4px">If the button does not work, paste this into your browser:</p>
       <p style="color:#666;font-size:13px;word-break:break-all;margin:0">${escapeHtml(action.url)}</p>`
    : ''
  return `<div style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;max-width:520px;margin:0 auto;padding:32px 24px;color:#111;line-height:1.55">
  <p style="font-weight:700;letter-spacing:.02em;margin:0 0 28px">${escapeHtml(branding.siteName)}</p>
  <h1 style="font-size:20px;margin:0 0 16px">${escapeHtml(heading)}</h1>
  ${body}
  ${button}
  <hr style="border:none;border-top:1px solid #e5e5e5;margin:32px 0 16px">
  <p style="color:#888;font-size:12px;margin:0">Questions? Reply to this email or write to ${escapeHtml(branding.supportEmail)}.</p>
</div>`
}

/** Hours, phrased for a human. Expiries here are short enough to stay whole. */
function hours(n: number): string {
  return n === 1 ? '1 hour' : `${n} hours`
}

export function verifyEmail(branding: Branding, url: string, expiresInHours: number): Rendered {
  const heading = `Confirm your email`
  const line = `Confirm this address to finish setting up your ${branding.siteName} account.`
  const expiry = `This link expires in ${hours(expiresInHours)} and can be used once.`
  // No name in the subject. A subject that greets someone by a name they just
  // typed is a subject an attacker can write, and the registration form is
  // open to anyone.
  return {
    subject: `Confirm your email · ${branding.siteName}`,
    text: [
      line,
      '',
      url,
      '',
      expiry,
      '',
      `If you did not create an account, ignore this email — nothing will happen.`,
    ].join('\n'),
    html: layout(
      branding,
      heading,
      `<p style="margin:0 0 8px">${escapeHtml(line)}</p>
       <p style="color:#666;font-size:13px;margin:0">${escapeHtml(expiry)} If you did not create an account, ignore this email — nothing will happen.</p>`,
      { label: 'Confirm email', url },
    ),
  }
}

export function resetPassword(branding: Branding, url: string, expiresInHours: number): Rendered {
  const heading = `Reset your password`
  const line = `Someone asked to reset the password for this ${branding.siteName} account.`
  const expiry = `This link expires in ${hours(expiresInHours)} and can be used once.`
  // "Someone asked", not "you asked". The recipient of an unrequested reset
  // mail did not ask, and telling them they did is how a phish reads.
  const ignore = `If that was not you, ignore this email. Your password will not change and nobody has been given access.`
  return {
    subject: `Reset your password · ${branding.siteName}`,
    text: [line, '', url, '', expiry, '', ignore].join('\n'),
    html: layout(
      branding,
      heading,
      `<p style="margin:0 0 8px">${escapeHtml(line)}</p>
       <p style="color:#666;font-size:13px;margin:0">${escapeHtml(expiry)} ${escapeHtml(ignore)}</p>`,
      { label: 'Reset password', url },
    ),
  }
}

/**
 * The double opt-in migration 0006 described and nothing ever sent (F135).
 *
 * Until someone follows this link their row stays `pending` and they are not
 * on the list. That is the whole point: the confirmation is the consent
 * record, and a schema that let a row reach `confirmed` any other way would
 * turn a form submission into a claim we cannot evidence.
 */
export function newsletterConfirm(branding: Branding, url: string): Rendered {
  const heading = `Confirm your subscription`
  const line = `Confirm this address to start receiving the ${branding.siteName} newsletter.`
  const ignore = `If you did not sign up, ignore this email — you will not be subscribed and we will not write again.`
  return {
    subject: `Confirm your subscription · ${branding.siteName}`,
    text: [line, '', url, '', ignore].join('\n'),
    html: layout(
      branding,
      heading,
      `<p style="margin:0 0 8px">${escapeHtml(line)}</p>
       <p style="color:#666;font-size:13px;margin:0">${escapeHtml(ignore)}</p>`,
      { label: 'Confirm subscription', url },
    ),
  }
}
