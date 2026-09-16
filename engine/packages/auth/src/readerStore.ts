/**
 * `ReaderStore` against `now_platform.engine.*` (migration 0007).
 *
 * The only file in the reader path that knows SQL, mirroring `store.ts`'s
 * relationship to `identity.ts` — which is what lets `reader.ts`'s lockout,
 * enumeration and expiry behaviour be tested with an in-memory double.
 *
 * Readers live in the **platform** database, not a city one: a person reads
 * Jakarta and Bali, and `newsletter_subscribers` already set that precedent in
 * migration 0006 for the same reason.
 */

import type pg from 'pg'

import type { StoredCredential } from './password.ts'
import type {
  EmailTokenKind,
  EmailTokenRecord,
  ReaderRecord,
  ReaderStatus,
  ReaderStore,
} from './reader.ts'

const COLUMNS = `id, email, email_norm, name, hash, salt,
                 email_verified_at, login_attempts, lock_until, status`

type Row = {
  id: string
  email: string
  email_norm: string
  name: string | null
  hash: string | null
  salt: string | null
  email_verified_at: string | Date | null
  login_attempts: number
  lock_until: string | Date | null
  status: string
}

function toDate(value: string | Date | null): Date | null {
  if (value === null) return null
  return value instanceof Date ? value : new Date(value)
}

function toReader(row: Row): ReaderRecord {
  return {
    id: row.id,
    email: row.email,
    emailNorm: row.email_norm,
    name: row.name,
    hash: row.hash,
    salt: row.salt,
    emailVerifiedAt: toDate(row.email_verified_at),
    loginAttempts: row.login_attempts,
    lockUntil: toDate(row.lock_until),
    status: row.status as ReaderStatus,
  }
}

export class PostgresReaderStore implements ReaderStore {
  private readonly pool: pg.Pool

  constructor(pool: pg.Pool) {
    this.pool = pool
  }

  async findByEmail(emailNorm: string): Promise<ReaderRecord | null> {
    const { rows } = await this.pool.query<Row>(
      `SELECT ${COLUMNS} FROM engine.identities WHERE email_norm = $1`,
      [emailNorm],
    )
    return rows[0] ? toReader(rows[0]) : null
  }

  async findById(id: string): Promise<ReaderRecord | null> {
    const { rows } = await this.pool.query<Row>(
      `SELECT ${COLUMNS} FROM engine.identities WHERE id = $1`,
      [id],
    )
    return rows[0] ? toReader(rows[0]) : null
  }

  async create(input: {
    email: string
    emailNorm: string
    name: string | null
    credential: StoredCredential
  }): Promise<ReaderRecord> {
    // ON CONFLICT DO NOTHING rather than letting the unique violation raise:
    // two registrations for the same address racing each other is ordinary,
    // and the loser should read the winner's row, not 500. The follow-up
    // SELECT covers that case.
    const { rows } = await this.pool.query<Row>(
      `INSERT INTO engine.identities (email, email_norm, name, hash, salt, status)
            VALUES ($1, $2, $3, $4, $5, 'active')
       ON CONFLICT (email_norm) DO NOTHING
         RETURNING ${COLUMNS}`,
      [input.email, input.emailNorm, input.name, input.credential.hash, input.credential.salt],
    )
    if (rows[0]) return toReader(rows[0])

    const existing = await this.findByEmail(input.emailNorm)
    if (!existing) throw new Error('insert reported a conflict but no row was found')
    return existing
  }

  async recordFailedAttempt(id: string, lockUntil: Date | null): Promise<void> {
    await this.pool.query(
      `UPDATE engine.identities
          SET login_attempts = login_attempts + 1,
              lock_until     = $2,
              updated_at     = now()
        WHERE id = $1`,
      [id, lockUntil],
    )
  }

  async clearFailedAttempts(id: string, lastLoginAt: Date): Promise<void> {
    await this.pool.query(
      `UPDATE engine.identities
          SET login_attempts = 0,
              lock_until     = NULL,
              last_login_at  = $2,
              updated_at     = now()
        WHERE id = $1`,
      [id, lastLoginAt],
    )
  }

  async setPassword(id: string, credential: StoredCredential): Promise<void> {
    await this.pool.query(
      `UPDATE engine.identities
          SET hash = $2, salt = $3, updated_at = now()
        WHERE id = $1`,
      [id, credential.hash, credential.salt],
    )
  }

  async markEmailVerified(id: string, at: Date): Promise<void> {
    // COALESCE: the first confirmation is the one that counts. Re-verifying
    // later (after a reset, say) should not rewrite when the address was
    // actually proven.
    await this.pool.query(
      `UPDATE engine.identities
          SET email_verified_at = COALESCE(email_verified_at, $2),
              updated_at        = now()
        WHERE id = $1`,
      [id, at],
    )
  }

  async createToken(input: {
    identityId: string
    kind: EmailTokenKind
    tokenHash: string
    expiresAt: Date
  }): Promise<void> {
    await this.pool.query(
      `INSERT INTO engine.identity_tokens (identity_id, kind, token_hash, expires_at)
            VALUES ($1, $2, $3, $4)`,
      [input.identityId, input.kind, input.tokenHash, input.expiresAt],
    )
  }

  async findTokenByHash(tokenHash: string): Promise<EmailTokenRecord | null> {
    const { rows } = await this.pool.query<{
      id: string
      identity_id: string
      kind: string
      expires_at: string | Date
      consumed_at: string | Date | null
    }>(
      `SELECT id, identity_id, kind, expires_at, consumed_at
         FROM engine.identity_tokens
        WHERE token_hash = $1`,
      [tokenHash],
    )
    const row = rows[0]
    if (!row) return null
    return {
      id: row.id,
      identityId: row.identity_id,
      kind: row.kind as EmailTokenKind,
      expiresAt: toDate(row.expires_at) as Date,
      consumedAt: toDate(row.consumed_at),
    }
  }

  async consumeToken(id: string, at: Date): Promise<void> {
    // `AND consumed_at IS NULL` makes redemption atomic: two clicks on the
    // same link racing each other cannot both mark it consumed, so the second
    // finds nothing to update. Checking in application code and writing
    // unconditionally would let both through.
    await this.pool.query(
      `UPDATE engine.identity_tokens
          SET consumed_at = $2
        WHERE id = $1 AND consumed_at IS NULL`,
      [id, at],
    )
  }

  async deleteTokens(identityId: string, kind: EmailTokenKind): Promise<void> {
    await this.pool.query(
      `DELETE FROM engine.identity_tokens WHERE identity_id = $1 AND kind = $2`,
      [identityId, kind],
    )
  }
}
