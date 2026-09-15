/**
 * Compatibility with Payload's local strategy.
 *
 * The fixtures below were produced by **Payload itself** (3.88.0), not by
 * `hashPassword` in this package. That distinction is the whole point: a test
 * that hashes with the same code it is verifying proves only that the code
 * agrees with itself, and would keep passing if both sides drifted from
 * Payload together. These pairs pin us to the real thing.
 *
 * To regenerate, in a Payload app:
 *   const { hash, salt } = await generatePasswordSaltHash({ password: '…' })
 */

import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { PBKDF2, hashPassword, verifyPassword } from '../src/password.ts'

// Produced by payload@3.88.0's own generatePasswordSaltHash, not by this
// package. This is the pin: if our pbkdf2 parameters ever drift from
// Payload's, this fixture stops verifying and the suite fails loudly rather
// than every staff password quietly breaking in production.
const PAYLOAD_FIXTURE = {
  password: 'correct horse battery staple',
  salt: '231555e15dc5d7502e6298a13be2e92d53dd6d9dee45ecb6663e28fe9b485141',
  hash:
    '3e21960bc1376cebf30f97dadc33068bb4364916b672c516b68b1fcebc1a59450380ed5f8b177f1020abedf72a34fe4' +
    '87d39e9b22d6f69e0a9bccaf3b7896ff03f8b4c67ea7b90c3e8dbcee9bc04af1e70b48eabb6af1b7aeefba700c40e34' +
    '3bad50c17f321afbd01d3dbba7268e01d13f25113d14aabefaf23075c2c97d7b7971efa8be88cb01474b171454a226f' +
    '15d3c47b54ebca1b2a948f2f20e315d252f164755f29d958ada75d4a56948d69e31da2fe2e33578a973f59b16a91420' +
    '4d071ab57a75f83d43f3edb7f80b2226356687771a91526a18b4a30637e450d033e43e486ad1454f31d94e0944d53a0' +
    '21d8f5ca315e12aff465ab09efdd13c67f26fbf50908ce50bd22a242fb404a1c3a60973317aaaea570d5601547e6484' +
    'e16e12606d6b2061b845b50a8a6b3bbdaa65d60c1dd464a4d1d5484f4beae4651e690c2efe367a9c81e5f96fca224e1' +
    'f2a4fe58eda05402716051cb8b6b0a6a395194b5d890833d568a5287773000495e11c147468c35a785b771c3e1ee2bd' +
    'c621ffd6595beda65bd8c01a9f982ab04ec1d06bbbe1ef736fae4daab4be37b6b2aba1750206d818a26fc48a6742c2a' +
    'bca862929d58c488f195ee1fea54cb40d237bbabac9ffa637f8acced5c466c108333a262ff70b7b9e9677c74a48bde8' +
    'd84836a0a1f6fa631b665852189b07a735b434b2207e17cc83428647cd2b88dc79f96caf3b',
}

describe('payload compatibility', () => {
  it('verifies a credential payload itself generated', async () => {
    assert.equal(PAYLOAD_FIXTURE.hash.length, 1024, 'fixture is 512 bytes, hex encoded')
    assert.equal(
      await verifyPassword(PAYLOAD_FIXTURE.password, PAYLOAD_FIXTURE),
      true,
      'our pbkdf2 parameters have drifted from payload — every stored password would break',
    )
  })

  it('rejects a wrong password against a payload-generated credential', async () => {
    assert.equal(await verifyPassword('wrong password entirely', PAYLOAD_FIXTURE), false)
    assert.equal(await verifyPassword('correct horse battery stapl', PAYLOAD_FIXTURE), false)
  })
})

describe('PBKDF2 parameters', () => {
  it('match payload 3.88.0 exactly', () => {
    // If any of these change, every stored credential stops verifying.
    assert.equal(PBKDF2.iterations, 25_000)
    assert.equal(PBKDF2.keylen, 512)
    assert.equal(PBKDF2.digest, 'sha256')
  })
})

describe('verifyPassword', () => {
  it('accepts the correct password', async () => {
    const { hash, salt } = await hashPassword('correct horse battery staple')
    assert.equal(await verifyPassword('correct horse battery staple', { hash, salt }), true)
  })

  it('rejects a wrong password', async () => {
    const { hash, salt } = await hashPassword('correct horse battery staple')
    assert.equal(await verifyPassword('Correct horse battery staple', { hash, salt }), false)
    assert.equal(await verifyPassword('', { hash, salt }), false)
    assert.equal(await verifyPassword('correct horse battery stapl', { hash, salt }), false)
  })

  it('rejects when the salt does not match the hash', async () => {
    const a = await hashPassword('same password')
    const b = await hashPassword('same password')
    // Same password, different salt -> different hash. Crossing them must fail.
    assert.equal(await verifyPassword('same password', { hash: a.hash, salt: b.salt }), false)
  })

  it('treats a missing credential as unauthenticatable, not an error', async () => {
    assert.equal(await verifyPassword('anything', { hash: null, salt: null }), false)
    assert.equal(await verifyPassword('anything', { hash: 'abc', salt: null }), false)
    assert.equal(await verifyPassword('anything', { hash: null, salt: 'abc' }), false)
    assert.equal(await verifyPassword('anything', { hash: '', salt: '' }), false)
  })

  it('rejects a malformed hash instead of throwing', async () => {
    // Buffer.from(<non-hex>, 'hex') truncates silently rather than throwing,
    // so a corrupted column must be caught by the length check.
    assert.equal(await verifyPassword('anything', { hash: 'zzzz', salt: 'aabb' }), false)
    assert.equal(await verifyPassword('anything', { hash: 'aabb', salt: 'aabb' }), false)
  })

  it('produces a credential of the shape payload stores', async () => {
    const { hash, salt } = await hashPassword('whatever')
    assert.equal(salt.length, 64, 'salt is 32 random bytes, hex encoded')
    assert.equal(hash.length, PBKDF2.keylen * 2, 'hash is keylen bytes, hex encoded')
    assert.match(hash, /^[0-9a-f]+$/)
    assert.match(salt, /^[0-9a-f]+$/)
  })

  it('generates a different salt every time', async () => {
    const a = await hashPassword('same')
    const b = await hashPassword('same')
    assert.notEqual(a.salt, b.salt)
    assert.notEqual(a.hash, b.hash)
  })
})
