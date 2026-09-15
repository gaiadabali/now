/**
 * Shared staff identity (Phase 1 of docs/ADMIN-CONSOLIDATION.md).
 *
 * `now_platform.public.users` is the single source of truth for who may sign
 * in and what role they hold. Each city database keeps a shadow projection
 * carrying email, name and role — never a credential — because Payload binds
 * exactly one database per instance and needs its `admin.user` collection
 * locally.
 *
 * This package deliberately stops at "is this person who they say they are,
 * and what is their role". Issuing the session is Payload's job; wiring it is
 * Phase 1's integration step.
 */

export { PBKDF2, hashPassword, verifyPassword, type StoredCredential } from './password.ts'
export {
  COMMERCE_ROLES,
  DEFAULT_LOCKOUT,
  EDITORIAL_ROLES,
  authenticate,
  hasAnyAccess,
  isCommerceRole,
  isEditorialRole,
  normaliseEmail,
  type AuthFailure,
  type AuthResult,
  type AuthenticateOptions,
  type AuthenticatedUser,
  type IdentityStore,
  type CommerceRole,
  type EditorialRole,
  type LockoutPolicy,
  type PlatformUser,
} from './identity.ts'
export { PostgresIdentityStore, createPool, upsertShadowUser } from './store.ts'
export {
  DEFAULT_SESSION_TTL_SECONDS,
  SESSION_COOKIE,
  issueSessionToken,
  sessionCookieOptions,
  verifySessionToken,
  type SessionClaims,
  type VerifyFailure,
  type VerifyResult,
} from './session.ts'
