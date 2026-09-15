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
  DEFAULT_LOCKOUT,
  STAFF_ROLES,
  authenticate,
  isStaffRole,
  normaliseEmail,
  type AuthFailure,
  type AuthResult,
  type AuthenticateOptions,
  type AuthenticatedUser,
  type IdentityStore,
  type LockoutPolicy,
  type PlatformUser,
  type StaffRole,
} from './identity.ts'
export { PostgresIdentityStore, createPool, upsertShadowUser } from './store.ts'
