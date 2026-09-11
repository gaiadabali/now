#!/usr/bin/env node
// Fast, browser-less regression test using jsdom. This complements — it does
// not replace — the real-browser verification run via Playwright during
// development (see README.md "Verification" section for that transcript).
//
// Run: node test/beacon.test.js   (or `npm test`)
'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { JSDOM } = require('jsdom');

const DIST = path.join(__dirname, '..', 'dist', 'beacon.min.js');
const SRC = fs.readFileSync(DIST, 'utf8');

let failures = 0;
let count = 0;
const tests = [];

// Registers a test; fn may be sync or async (return a Promise) — the runner
// at the bottom of this file awaits each one in turn.
function test(name, fn) {
  tests.push({ name, fn });
}

async function runAll() {
  for (const { name, fn } of tests) {
    count++;
    try {
      await fn();
      console.log('  ok  - ' + name);
    } catch (e) {
      failures++;
      console.log('FAIL  - ' + name);
      console.log('        ' + (e && e.message ? e.message : e));
    }
  }
  console.log('\n' + (count - failures) + '/' + count + ' passed');
  process.exit(failures ? 1 : 0);
}

// Builds a fresh jsdom window with the beacon script "installed" via a
// <script> tag (so document.currentScript / data-* attributes resolve the
// same way they would on a real page), plus stubbed transports so no real
// network call ever leaves the test process.
function makeBeacon(opts) {
  opts = opts || {};
  const attrs = Object.assign({
    'data-site': 'test',
    'data-entity': 'article-1',
    'data-entity-type': 'article',
    'data-surface': 'article',
    'data-endpoint': 'https://engine.test/v1/test/events'
  }, opts.attrs || {});

  const attrStr = Object.keys(attrs).map((k) => k + '="' + attrs[k] + '"').join(' ');
  const html = '<!doctype html><html><body><script id="tag" ' + attrStr + '></script></body></html>';

  const dom = new JSDOM(html, {
    url: opts.url || 'https://reader.test/articles/rooftop-bars',
    runScripts: 'outside-only'
  });
  const window = dom.window;
  const document = window.document;

  Object.defineProperty(document, 'currentScript', {
    value: document.getElementById('tag'),
    configurable: true
  });

  if (opts.doNotTrack) {
    Object.defineProperty(window.navigator, 'doNotTrack', { value: '1', configurable: true });
  }

  if (opts.blockCookies) {
    Object.defineProperty(document, 'cookie', {
      get() { return ''; },
      set() { throw new Error('cookies blocked by test'); },
      configurable: true
    });
  }

  const sentBeacons = [];
  const fetchCalls = [];
  window.navigator.sendBeacon = function (url, body) {
    sentBeacons.push({ url: url, body: body });
    return true;
  };
  window.fetch = function (url, init) {
    fetchCalls.push({ url: url, body: init && init.body });
    return Promise.resolve({ ok: true });
  };

  window.eval(SRC);

  return { window: window, document: document, sentBeacons: sentBeacons, fetchCalls: fetchCalls };
}

function lastBody(env) {
  if (env.fetchCalls.length) return JSON.parse(env.fetchCalls[env.fetchCalls.length - 1].body);
  if (env.sentBeacons.length) return JSON.parse(env.sentBeacons[env.sentBeacons.length - 1].body);
  return null;
}

// sendBeacon's body is a Blob in real browsers and in jsdom; reading it back
// out is async, so unload-path assertions use this instead of lastBody().
async function lastBeaconBody(env) {
  const entry = env.sentBeacons[env.sentBeacons.length - 1];
  assert.ok(entry, 'expected at least one sendBeacon call');
  const text = typeof entry.body === 'string' ? entry.body : await entry.body.text();
  return JSON.parse(text);
}

// ---------------------------------------------------------------------

test('NOWB global is installed and marked loaded', () => {
  const env = makeBeacon();
  assert.strictEqual(typeof env.window.NOWB, 'function');
  assert.strictEqual(env.window.NOWB.__loaded, true);
});

test('view fires automatically on boot and reaches the transport on flush', () => {
  const env = makeBeacon();
  env.window.NOWB('flush');
  const body = lastBody(env);
  assert.ok(body, 'expected a flushed batch');
  const view = body.interactions.find((e) => e.kind === 'view');
  assert.ok(view, 'expected a view interaction');
  assert.strictEqual(view.entity_type, 'article');
  assert.strictEqual(view.entity_id, 'article-1');
  assert.strictEqual(view.surface, 'article');
});

test('interaction payload uses exactly the contracted field names', () => {
  const env = makeBeacon();
  env.window.NOWB('track', 'click', { entityId: 'place:1', rail: 'complementary', position: 2 });
  env.window.NOWB('flush');
  const body = lastBody(env);
  const click = body.interactions.find((e) => e.kind === 'click');
  assert.ok(click);
  const allowed = new Set([
    'anon_id', 'user_id', 'session_id', 'entity_type', 'entity_id',
    'kind', 'surface', 'rail', 'position', 'dwell_ms', 'scroll_pct',
    'referrer', 'utm', 'device', 'ts'
  ]);
  for (const key of Object.keys(click)) {
    assert.ok(allowed.has(key), 'unexpected field on interaction: ' + key);
  }
  for (const required of ['anon_id', 'session_id', 'entity_type', 'entity_id', 'kind', 'surface', 'device', 'ts']) {
    assert.ok(click[required] !== undefined, 'missing required field: ' + required);
  }
  assert.strictEqual(click.rail, 'complementary');
  assert.strictEqual(click.position, 2);
});

test('impression payload uses exactly the contracted field names', () => {
  const env = makeBeacon();
  env.window.NOWB('impression', { surface: 'article', rail: 'nearby', entityId: 'place:9', position: 1 });
  env.window.NOWB('flush');
  const body = lastBody(env);
  const imp = body.impressions[0];
  assert.ok(imp);
  const allowed = ['session_id', 'anon_id', 'surface', 'rail', 'entity_id', 'position', 'ts'];
  assert.deepStrictEqual(Object.keys(imp).sort(), allowed.slice().sort());
});

test('kind enum is restricted to the contracted values', () => {
  const env = makeBeacon();
  const valid = ['view', 'scroll', 'dwell', 'click', 'outbound', 'search', 'exit', 'thumbs_down'];
  env.window.NOWB('track', 'click', {});
  env.window.NOWB('thumbsDown', {});
  env.window.NOWB('flush');
  const body = lastBody(env);
  for (const e of body.interactions) {
    assert.ok(valid.indexOf(e.kind) !== -1, 'invalid kind emitted: ' + e.kind);
  }
});

test('search query travels in entity_id/entity_type, no new field added', () => {
  const env = makeBeacon({ url: 'https://reader.test/search?q=rooftop+bar' });
  env.window.NOWB('flush');
  const body = lastBody(env);
  const search = body.interactions.find((e) => e.kind === 'search');
  assert.ok(search, 'expected a search interaction from ?q=');
  assert.strictEqual(search.entity_type, 'search_query');
  assert.strictEqual(search.entity_id, 'rooftop bar');
});

test('DNT: no network call ever leaves the page, even after an explicit flush', () => {
  const env = makeBeacon({ doNotTrack: true });
  env.window.NOWB('impression', { surface: 'article', rail: 'nearby', entityId: 'x', position: 1 });
  env.window.NOWB('track', 'click', {});
  env.window.NOWB('flush');
  assert.strictEqual(env.sentBeacons.length, 0);
  assert.strictEqual(env.fetchCalls.length, 0);
});

test('consent=denied: no network call after the user opts out', () => {
  const env = makeBeacon();
  env.window.NOWB('consent', 'denied');
  env.window.NOWB('track', 'click', {});
  env.window.NOWB('flush');
  assert.strictEqual(env.sentBeacons.length, 0);
  assert.strictEqual(env.fetchCalls.length, 0);
});

test('cookies blocked: never throws, still tracks with a memory-only anon_id', () => {
  const env = makeBeacon({ blockCookies: true });
  assert.doesNotThrow(() => {
    env.window.NOWB('impression', { surface: 'article', rail: 'nearby', entityId: 'x', position: 1 });
    env.window.NOWB('flush');
  });
  const body = lastBody(env);
  assert.ok(body.impressions[0].anon_id, 'expected a generated anon_id even without cookies');
});

test('exit path (simulated pagehide) sends via sendBeacon, not fetch', async () => {
  const env = makeBeacon();
  env.window.dispatchEvent(new env.window.Event('pagehide'));
  assert.strictEqual(env.fetchCalls.length, 0, 'unload flush must prefer sendBeacon');
  const body = await lastBeaconBody(env);
  const kinds = body.interactions.map((e) => e.kind);
  assert.ok(kinds.indexOf('dwell') !== -1, 'expected a final dwell event');
  assert.ok(kinds.indexOf('exit') !== -1, 'expected a final exit event');
});

test('a thrown error inside a click handler never escapes to the host page', () => {
  const env = makeBeacon();
  // Malformed anchor (href getter throws) exercises the safe() wrapper.
  const a = env.document.createElement('a');
  Object.defineProperty(a, 'href', { get() { throw new Error('boom'); } });
  env.document.body.appendChild(a);
  assert.doesNotThrow(() => {
    a.dispatchEvent(new env.window.MouseEvent('click', { bubbles: true }));
  });
});

// ---------------------------------------------------------------------

runAll();
