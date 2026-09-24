/**
 * Pure, framework-free commerce write-access predicates (S5.2).
 *
 * Split out of `lib/auth.ts` for exactly one reason: `lib/auth.ts` imports
 * `next/headers` and `next/navigation`, which only resolve inside Next's own
 * build/runtime — importing that module from a plain `node --test` process
 * (this repo's whole test runner; see `test/html.test.ts`) throws
 * `ERR_MODULE_NOT_FOUND` before a single assertion runs:
 *
 *   Cannot find module '.../node_modules/next/headers' imported from
 *   '.../src/lib/auth.ts'
 *
 * The actual DECISION these functions make has nothing to do with Next; it
 * is ordinary data logic, and docs/SURFACES-PLAN.md §6 calls the tests for
 * it "the deliverable, not an afterthought" — so the logic lives somewhere a
 * test can import directly, no Next.js request in sight. `lib/auth.ts`
 * re-exports everything here, so every existing and future caller keeps
 * importing from `@/lib/auth` exactly as before; this file is never imported
 * from application code, only from `lib/auth.ts` and from
 * `test/partnershipAccess.test.ts`.
 */

/** The one shape these predicates need from a signed-in user. */
export type CommerceRoleUser = { commerceRole?: string }

/** May this user change partnership state at all — either dimension below? */
export function canManagePartners(user: CommerceRoleUser): boolean {
  return user.commerceRole === 'admin' || user.commerceRole === 'partner_manager'
}

/**
 * Which site THIS process is allowed to let a `partner_manager` write.
 *
 * A pure read of `SITE_SLUG`, not a decision — kept as its own one-line
 * function so `canWritePartnershipForSite` below never reaches into
 * `process.env` itself and stays testable with a plain string argument (see
 * that function's own comment for why that separation matters here
 * specifically). Same fact `lib/site.ts`'s `requireSlug()` reads, for the
 * same reason: this process serves exactly one city (ARCHITECTURE.md §3.5).
 */
export function commerceCurrentSiteSlug(): string {
  return process.env.SITE_SLUG ?? ''
}

/**
 * Site-scoped write authority for partnerships (S5.2).
 *
 * **Why `commerceRole` alone stopped being enough the moment a write
 * existed.** Commerce data is platform-wide and reachable from *either*
 * city's admin session — docs/ADMIN-CONSOLIDATION.md calls this out by name:
 * "a compromised Jakarta admin session can read Bali's partner terms...
 * afterwards it is prevented by access rules alone." That sentence was
 * written about reads, when the console was still four read-only tables. The
 * moment S5.2 adds a write, the same sentence describes an edit, not a leak —
 * a `partner_manager` who signs in to look after one city's partner roster
 * can, with nothing stopping them, open the other city's `/team-editor` (same
 * login, same role, only `SITE_SLUG` differs) and change contract terms that
 * were never theirs to touch.
 *
 * So the two commerce roles that can write at all (`canManagePartners`) do
 * not get the same reach:
 *
 * - **`admin`** may write any site's partnerships. Commercial strategy
 *   genuinely spans cities — a hotel group's deal is negotiated once and
 *   applies everywhere the group has a property — so the platform-wide role
 *   stays platform-wide.
 * - **`partner_manager`** may write only the site *this process* serves.
 *   Not the site named anywhere in a form field or a request body — the one
 *   fact a request cannot forge, because it is which container answered it.
 *
 * `viewer`, `none`, and no commerce role at all remain unable to write
 * anything, exactly as `canManagePartners` already said.
 *
 * A pure function of its three arguments, deliberately: see
 * `test/partnershipAccess.test.ts` for every case this ticket names —
 * author, viewer, wrong-site `partner_manager`, right-site `partner_manager`,
 * admin, and unauthenticated (`user === null`).
 */
export function canWritePartnershipForSite(
  user: CommerceRoleUser | null,
  currentSiteSlug: string,
  targetSiteSlug: string,
): boolean {
  if (!user) return false
  if (!canManagePartners(user)) return false
  if (user.commerceRole === 'admin') return true
  return targetSiteSlug === currentSiteSlug && currentSiteSlug !== ''
}
