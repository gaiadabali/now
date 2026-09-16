# @now/mailer

E8.0 — transactional email. [docs/READER-IDENTITY.md](../../../docs/READER-IDENTITY.md).

## Why this exists

Nothing in the stack could send mail. Not "had a misconfigured provider" —
there was no nodemailer, no SDK, no SMTP config anywhere. That blocked email
verification and password reset, which is why it is E8.0 rather than a
sub-task of the auth work.

It also meant something already shipped was quietly broken:

> `lib/newsletter.ts` inserts every subscriber as `status='pending'` and no
> code path has ever sent the confirmation or moved a row to `'confirmed'`.
> Migration 0006's three states describe a double opt-in that was never built.
> (F135)

So the newsletter confirmation is one of the three templates here, not an
afterthought.

## SMTP, not a provider SDK

Every transactional provider worth using — SES, Postmark, Resend, SendGrid,
Mailgun — speaks SMTP, and so does a self-hosted relay. One transport covers
all of them:

- changing provider is a change of environment variables, not of code
- local development points the same object at Mailpit
- there is no vendor client to keep current

A provider SDK would buy webhooks and open-rate analytics that this package
does not use, in exchange for a lock-in it does not need.

`nodemailer` does the protocol. That is not a contradiction of `@now/auth`'s
`password.ts`, which reimplements PBKDF2 by hand — that file *must* match
Payload byte-for-byte and is one well-specified function. SMTP is connection
management, STARTTLS negotiation, AUTH mechanisms, MIME assembly and encoding,
and subtly wrong MIME renders as raw source in one client and fine in another.

## The transport is an interface

Same seam `@now/auth` puts at `IdentityStore`, for the same reason: the part
worth testing is the policy above it — what a reset mail says, how long a link
lives, what a send failure does to a registration — and none of that should
need a network.

| Transport | For |
|---|---|
| `SmtpTransport` | real sending, any provider |
| `MemoryTransport` | tests; keeps every message so content can be asserted |
| `ConsoleTransport` | local dev with no SMTP server; prints the body, link included |

`ConsoleTransport` is **refused under `NODE_ENV=production`** by
`createTransportFromEnv`. In development, printing verification links to
stdout is the feature. In production it is an outage that looks like success:
every registration appears to work, nothing is delivered, and the logs fill
with live single-use credentials. Failing at startup is the cheapest place to
find that out.

## links.ts is the security-critical file

A verification or reset link is a bearer credential — whoever opens it is
treated as the account holder. So *which host the link points at* is a
security question.

The obvious implementation reads the request's `Host` header. That is
host-header injection, and it is routinely exploited: an attacker requests a
password reset for someone else's address with `Host: attacker.example`, the
victim receives a genuine mail from the real system, clicks, and hands their
single-use token to the attacker. The mail is authentic — that is what makes
it work.

`Host` is never consulted. The base URL is configuration, `http://` is refused
unless a caller explicitly opts in, and a site with no configured base cannot
send links at all.

## Usage

```ts
import { Mailer, buildLink, createTransportFromEnv, verifyEmail } from '@now/mailer'

const selected = createTransportFromEnv()
if (!selected.ok) throw new Error(selected.detail)   // fail at startup, not at send

const mailer = new Mailer({
  transport: selected.transport,
  from: { email: 'hello@gaiada.com', name: 'NOW! Jakarta' },
})

const link = buildLink(process.env.SITE_BASE_URL, '/verify', { token })
if (!link.ok) throw new Error(`cannot build verification link: ${link.reason}`)

const result = await mailer.send({
  to: { email: reader.email },
  ...verifyEmail({ siteName: 'NOW! Jakarta', supportEmail: 'hello@gaiada.com' }, link.url, 24),
  tag: 'verify_email',
})
if (!result.ok) {
  // The account exists; the mail did not go. Offer a resend — do not 500 and
  // lose the registration.
}
```

`send` returns a result rather than throwing, because a failed verification
mail is a decision the caller has to make.

## Environment

| Var | Default | Notes |
|---|---|---|
| `MAIL_TRANSPORT` | `smtp` if `SMTP_HOST` set, else `console` | `smtp` \| `console` |
| `SMTP_HOST` | — | required for `smtp` |
| `SMTP_PORT` | `587` | |
| `SMTP_SECURE` | `true` when port is 465 | implicit TLS vs STARTTLS |
| `SMTP_USER` / `SMTP_PASSWORD` | — | omit both for an unauthenticated relay |
| `SMTP_ALLOW_SELF_SIGNED` | `false` | local relays only; ignored in production |

**Production is Google Workspace**, because that is what `gaiada.com`'s DNS
already says. Checked live 2026-09-16 rather than inferred from the registrar:

```
MX    gaiada.com        ->  smtp.google.com (1)
TXT   gaiada.com        ->  v=spf1 include:_spf.google.com ~all
TXT   _dmarc.gaiada.com ->  v=DMARC1; p=none; ...; adkim=s; aspf=s
```

SPF authorises Google and nothing else, and DMARC asks for strict alignment on
both legs — so any other provider fails SPF and lands in spam, which from a
reader's side is indistinguishable from no mail being sent.

```
MAIL_TRANSPORT=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465                  # implicit TLS; SMTP_SECURE is derived from it
SMTP_USER=hello@gaiada.com     # a real Workspace mailbox
SMTP_PASSWORD=…                # an APP PASSWORD, not the account password
```

2,000 messages/day. `smtp-relay.gmail.com` allows 10,000 and authenticates by
IP if that ever binds. `MAIL_FROM_EMAIL` must align with `SMTP_USER` — `aspf=s`
is strict.

⚠️ **DKIM is not published for the domain** (`google._domainkey.gaiada.com`
does not resolve) while DMARC already asks for strict DKIM alignment. `p=none`
means nothing is rejected yet, but every message fails the DKIM leg of its own
policy. Enable it in Workspace admin before that policy is tightened.

Local development:

```bash
docker compose up -d mailpit     # SMTP on :1025, UI on http://localhost:8025
SMTP_HOST=localhost SMTP_PORT=1025 npm run dev
```

## Tests

```bash
npm test --workspace @now/mailer     # 36, no network
```

Mostly attack tests: header injection refused rather than stripped, origin
preserved against absolute and protocol-relative paths, query smuggling on the
configured base, console-in-production refused, and the transport name proven
not to carry a credential into the logs.

Verified end to end against a real Mailpit SMTP server on 2026-09-16 —
`verify()` handshake, delivery, both MIME parts present, link in both.

## Not built yet

| | |
|---|---|
| Bounce and complaint handling | needs a provider webhook; until then a hard bounce is invisible |
| Send-rate limiting | per-address throttling belongs above this package, at the route |
| Localisation | templates are English only; `Branding` is the seam a locale would enter through |
