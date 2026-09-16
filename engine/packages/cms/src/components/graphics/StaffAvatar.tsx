/**
 * The signed-in editor's mark, top right of every admin screen.
 *
 * Replaces Payload's default, which is a **Gravatar**: it MD5s the account's
 * email address and fetches an image from gravatar.com on every admin page.
 * That is a third-party request carrying a hash of staff email, made from a
 * CMS whose whole identity story was deliberately pulled in-house
 * (docs/ADMIN-CONSOLIDATION.md), to render a grey silhouette for anyone who
 * has never signed up there — which is everyone here. It was leaking
 * something for nothing.
 *
 * A monogram costs no request and is the same shape the brand already uses:
 * ink disc, one letter, the display serif.
 *
 * `user` arrives from Payload's serverProps. The shadow row carries `name`
 * for anyone whose platform record has one and `email` for everyone, so the
 * initial comes from the first that is present.
 */

type AvatarUser = { email?: string; name?: string } | null | undefined

function initialOf(user: AvatarUser): string {
  const source = user?.name?.trim() || user?.email?.trim() || ''
  // `[...source]` rather than `source[0]`: a name starting with an astral
  // character (an emoji, some scripts) would otherwise render half a code
  // point and a replacement box.
  const first = [...source][0]
  return first ? first.toUpperCase() : '·'
}

export function StaffAvatar({ user }: { user?: AvatarUser }) {
  return (
    <span aria-hidden="true" className="now-avatar">
      {initialOf(user)}
    </span>
  )
}
