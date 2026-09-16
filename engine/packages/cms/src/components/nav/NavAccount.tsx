/**
 * Who is signed in, and the way out — pinned to the foot of the sidebar.
 *
 * Payload's nav has a `nav__controls` slot for exactly this and ships it
 * empty, so the sidebar ended with roughly 600px of nothing below the last
 * collection. Meanwhile the only route to signing out was a link inside the
 * account menu behind the avatar, which is not where anyone looks.
 *
 * Identity matters more here than in a single-tenant CMS: one account opens
 * every city (docs/ADMIN-CONSOLIDATION.md), and the editorial role decides
 * what the screen will let you do. Showing the role means a permission
 * surprise — "why can't I publish?" — is answerable without leaving the page.
 *
 * Renders in `admin.components.afterNavLinks`.
 */

type NavUser = { email?: string; name?: string; role?: string } | null | undefined

/** `author` and `none` read alike to someone who has just been demoted. */
const ROLE_LABEL: Record<string, string> = {
  admin: 'Administrator',
  editor: 'Editor',
  author: 'Author — drafts only',
  none: 'No editorial access',
}

function initialOf(user: NavUser): string {
  const source = user?.name?.trim() || user?.email?.trim() || ''
  const first = [...source][0]
  return first ? first.toUpperCase() : '·'
}

export function NavAccount({ user }: { user?: NavUser }) {
  if (!user) return null

  const role = user.role ? (ROLE_LABEL[user.role] ?? user.role) : null

  return (
    <div className="now-nav-account">
      <div className="now-nav-account__who">
        <span aria-hidden="true" className="now-avatar now-avatar--nav">
          {initialOf(user)}
        </span>
        <span className="now-nav-account__names">
          {/* `title` because an address long enough to be truncated is
              exactly the one somebody needs to read in full. */}
          <span className="now-nav-account__name" title={user.email ?? undefined}>
            {user.name?.trim() || user.email}
          </span>
          {role ? <span className="now-nav-account__role">{role}</span> : null}
        </span>
      </div>

      {/* A plain link, not a form: /team-editor/logout answers GET, because
          the thing Payload's own nav points at is an anchor. */}
      <a className="now-nav-account__out" href="/team-editor/logout">
        Sign out
      </a>
    </div>
  )
}
