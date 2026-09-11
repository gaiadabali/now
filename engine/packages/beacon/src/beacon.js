/*!
 * NOW! Engine beacon — vanilla JS, zero dependencies.
 * Payload contract: engine/packages/beacon/README.md
 *
 * Namespaced global: window.NOWB
 * Never throws into the host page — every public entry point is wrapped.
 */
(function (win, doc) {
  'use strict';

  // Guard against double-inclusion (theme + plugin both loading it, etc).
  if (win.NOWB && win.NOWB.__loaded) return;

  // ---------------------------------------------------------------------
  // Config resolution — from the <script> tag's data-* attributes.
  // ---------------------------------------------------------------------
  var CURRENT_SCRIPT = doc.currentScript;

  function attr(name, fallback) {
    if (!CURRENT_SCRIPT) return fallback;
    var v = CURRENT_SCRIPT.getAttribute(name);
    return v == null || v === '' ? fallback : v;
  }

  var cfg = {
    site: attr('data-site', ''),
    entity: attr('data-entity', ''),
    entityType: attr('data-entity-type', 'article'),
    surface: attr('data-surface', 'article'),
    endpoint: attr('data-endpoint', ''), // default derived below
    consent: attr('data-consent', null), // 'granted' | 'denied' | null (unset)
    debug: attr('data-debug', null) === 'true'
  };

  if (!cfg.endpoint) {
    // Default: same script origin, /v1/{site}/events
    var src = (CURRENT_SCRIPT && CURRENT_SCRIPT.src) || '';
    var m = /^(https?:\/\/[^/]+)/i.exec(src);
    var origin = m ? m[1] : '';
    cfg.endpoint = origin + '/v1/' + encodeURIComponent(cfg.site || 'default') + '/events';
  }

  // ---------------------------------------------------------------------
  // Constants
  // ---------------------------------------------------------------------
  var COOKIE_ANON = 'nowb_aid';
  var ANON_MAX_AGE_S = 60 * 60 * 24 * 365; // 1 year
  var SESSION_KEY = 'nowb_sid';
  var SESSION_TS_KEY = 'nowb_sid_ts';
  var SESSION_WINDOW_MS = 30 * 60 * 1000; // 30-minute sliding window
  var FLUSH_INTERVAL_MS = 5000;
  var FLUSH_SIZE = 10;
  var SCROLL_MILESTONES = [25, 50, 75, 100];
  var MAX_QUEUE = 200; // hard cap so a runaway page can't leak memory

  // ---------------------------------------------------------------------
  // Small safe utilities — everything here must never throw.
  // ---------------------------------------------------------------------
  function now() { return Date.now(); }

  function noop() {}

  function safe(fn) {
    return function () {
      try { return fn.apply(this, arguments); } catch (e) { warn(e); }
    };
  }

  function warn(e) {
    if (cfg.debug && win.console && win.console.warn) {
      try { win.console.warn('[nowb]', e); } catch (e2) { /* truly give up */ }
    }
  }

  function generateUUID() {
    // Generate a valid RFC4122 v4 UUID. Uses crypto.randomUUID() if available
    // (modern browsers), falls back to a deterministic UUID v4 if not.
    try {
      if (win.crypto && win.crypto.randomUUID) {
        return win.crypto.randomUUID();
      }
    } catch (e) { /* fall through to fallback */ }

    // Fallback: generate UUID v4 format manually
    // Format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx where x is hex, y is [89ab]
    var bytes;
    try {
      if (win.crypto && win.crypto.getRandomValues) {
        bytes = new Uint8Array(16);
        win.crypto.getRandomValues(bytes);
      }
    } catch (e) { /* fall through to Math.random */ }

    var hex = '';
    if (bytes) {
      for (var i = 0; i < bytes.length; i++) {
        var b = bytes[i];
        hex += (b < 16 ? '0' : '') + b.toString(16);
      }
    } else {
      // Last resort: use Math.random
      for (var i = 0; i < 32; i++) {
        hex += Math.floor(Math.random() * 16).toString(16);
      }
    }

    // Format as UUID v4: 8-4-4-4-12
    return hex.slice(0, 8) + '-' +
           hex.slice(8, 12) + '-' +
           '4' + hex.slice(13, 16) + '-' +
           (parseInt(hex[16], 16) | 0x8).toString(16) + hex.slice(17, 20) + '-' +
           hex.slice(20, 32);
  }

  function isValidUUID(str) {
    // Check if string matches RFC4122 UUID format (8-4-4-4-12 hex digits)
    if (!str || typeof str !== 'string') return false;
    var uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    return uuidRegex.test(str);
  }

  // ---------------------------------------------------------------------
  // Cookie helpers — degrade to an in-memory value if cookies are blocked.
  // ---------------------------------------------------------------------
  var cookiesWork = null;

  function cookiesAvailable() {
    if (cookiesWork !== null) return cookiesWork;
    try {
      var testKey = '__nowb_t';
      doc.cookie = testKey + '=1; max-age=60; SameSite=Lax';
      cookiesWork = doc.cookie.indexOf(testKey + '=1') !== -1;
      // clean up test cookie
      doc.cookie = testKey + '=; max-age=0';
    } catch (e) {
      cookiesWork = false;
    }
    return cookiesWork;
  }

  function getCookie(name) {
    try {
      var parts = doc.cookie ? doc.cookie.split('; ') : [];
      for (var i = 0; i < parts.length; i++) {
        var eq = parts[i].indexOf('=');
        if (eq === -1) continue;
        if (parts[i].substring(0, eq) === name) {
          return decodeURIComponent(parts[i].substring(eq + 1));
        }
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  function setCookie(name, value, maxAgeS) {
    try {
      var secure = win.location && win.location.protocol === 'https:' ? '; Secure' : '';
      doc.cookie = name + '=' + encodeURIComponent(value) +
        '; path=/; max-age=' + maxAgeS + '; SameSite=Lax' + secure;
    } catch (e) { /* ignore — falls back to memory */ }
  }

  // ---------------------------------------------------------------------
  // Session storage helpers — also degrade gracefully.
  // ---------------------------------------------------------------------
  function storageGet(key) {
    try { return win.sessionStorage.getItem(key); } catch (e) { return null; }
  }
  function storageSet(key, value) {
    try { win.sessionStorage.setItem(key, value); } catch (e) { /* ignore */ }
  }

  // In-memory fallbacks, used only when both cookies and storage are blocked.
  var memAnonId = null;
  var memSessionId = null;
  var memSessionTs = null;

  // ---------------------------------------------------------------------
  // Privacy gate — Do Not Track + explicit consent flag.
  // ---------------------------------------------------------------------
  function dntEnabled() {
    var dnt = win.doNotTrack || (nav().doNotTrack) || win.externalDoNotTrack;
    return dnt === '1' || dnt === 'yes' || dnt === true;
  }

  function nav() { return win.navigator || {}; }

  function consentDenied() {
    // Explicit opt-out wins. Absence of a consent attribute does NOT block —
    // callers that need strict opt-in should set data-consent="denied" until
    // the user accepts, then call NOWB('consent', 'granted').
    return runtimeConsent === 'denied' || (runtimeConsent === null && cfg.consent === 'denied');
  }

  var runtimeConsent = null; // set via public API, overrides data-consent

  function isDisabled() {
    return dntEnabled() || consentDenied();
  }

  // ---------------------------------------------------------------------
  // Identity — anon_id (1yr cookie) + session_id (30-min sliding window).
  // ---------------------------------------------------------------------
  function getAnonId() {
    if (cookiesAvailable()) {
      var existing = getCookie(COOKIE_ANON);
      if (existing) return existing;
      var fresh = generateUUID();
      setCookie(COOKIE_ANON, fresh, ANON_MAX_AGE_S);
      return fresh;
    }
    if (!memAnonId) memAnonId = generateUUID();
    return memAnonId;
  }

  function getSessionId() {
    var t = now();
    var storedId = storageGet(SESSION_KEY);
    var storedTs = parseInt(storageGet(SESSION_TS_KEY), 10);

    if (!storedId || !storedTs) {
      storedId = memSessionId;
      storedTs = memSessionTs;
    }

    var expired = !storedTs || (t - storedTs) > SESSION_WINDOW_MS;
    var id = expired || !storedId ? generateUUID() : storedId;

    storageSet(SESSION_KEY, id);
    storageSet(SESSION_TS_KEY, String(t));
    memSessionId = id;
    memSessionTs = t;
    return id;
  }

  function touchSession() {
    // Slides the 30-minute window forward on activity.
    memSessionTs = now();
    storageSet(SESSION_TS_KEY, String(memSessionTs));
  }

  // ---------------------------------------------------------------------
  // Device classification — coarse only, no fingerprinting.
  // ---------------------------------------------------------------------
  function device() {
    var ua = nav().userAgent || '';
    if (/Mobi|Android|iPhone/i.test(ua)) return 'mobile';
    if (/iPad|Tablet/i.test(ua)) return 'tablet';
    return 'desktop';
  }

  // ---------------------------------------------------------------------
  // UTM capture — from the landing URL only, read once per session.
  // ---------------------------------------------------------------------
  function currentUtm() {
    try {
      var qs = win.location.search || '';
      if (qs.indexOf('utm_') === -1) return undefined;
      var params = new URLSearchParams(qs);
      var utm = {};
      var keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];
      var any = false;
      for (var i = 0; i < keys.length; i++) {
        var v = params.get(keys[i]);
        if (v) { utm[keys[i].replace('utm_', '')] = v; any = true; }
      }
      return any ? utm : undefined;
    } catch (e) {
      return undefined;
    }
  }

  // ---------------------------------------------------------------------
  // Queue + transport
  // ---------------------------------------------------------------------
  var interactionQueue = [];
  var impressionQueue = [];
  var flushTimer = null;
  var unloading = false;

  function enqueueInteraction(evt) {
    if (isDisabled()) return;
    if (interactionQueue.length >= MAX_QUEUE) interactionQueue.shift();
    interactionQueue.push(evt);
    maybeFlush();
  }

  function enqueueImpression(evt) {
    if (isDisabled()) return;
    if (impressionQueue.length >= MAX_QUEUE) impressionQueue.shift();
    impressionQueue.push(evt);
    maybeFlush();
  }

  function maybeFlush() {
    if (interactionQueue.length + impressionQueue.length >= FLUSH_SIZE) {
      flush();
    } else {
      scheduleFlush();
    }
  }

  function scheduleFlush() {
    if (flushTimer) return;
    flushTimer = win.setTimeout(function () {
      flushTimer = null;
      flush();
    }, FLUSH_INTERVAL_MS);
  }

  function flush(useBeacon) {
    if (!interactionQueue.length && !impressionQueue.length) return;
    if (!cfg.site || !cfg.endpoint) return; // no-op cleanly if unconfigured

    var body = {
      interactions: interactionQueue,
      impressions: impressionQueue
    };
    interactionQueue = [];
    impressionQueue = [];

    var json;
    try {
      json = JSON.stringify(body);
    } catch (e) {
      warn(e);
      return;
    }

    var sentViaBeacon = false;
    if (useBeacon && nav().sendBeacon) {
      try {
        var blob;
        try {
          blob = new win.Blob([json], { type: 'application/json' });
        } catch (e) {
          blob = json; // very old browsers: sendBeacon accepts a string too
        }
        sentViaBeacon = nav().sendBeacon(cfg.endpoint, blob);
      } catch (e) {
        warn(e);
      }
    }

    if (!sentViaBeacon) {
      try {
        if (win.fetch) {
          win.fetch(cfg.endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: json,
            keepalive: !!useBeacon,
            credentials: 'omit'
          })['catch'](noop);
        } else if (win.XMLHttpRequest) {
          var xhr = new win.XMLHttpRequest();
          xhr.open('POST', cfg.endpoint, true);
          xhr.setRequestHeader('Content-Type', 'application/json');
          xhr.send(json);
        }
      } catch (e) {
        warn(e);
      }
    }
  }

  // ---------------------------------------------------------------------
  // Event builders — enforce the fixed payload contract field names.
  // ---------------------------------------------------------------------
  var pageEnteredAt = now();
  var maxScrollPct = 0;
  var reportedMilestones = {};
  var userId; // set only via public API — never inferred

  function baseFields() {
    var fields = {
      anon_id: getAnonId(),
      session_id: getSessionId(),
      device: device(),
      referrer: doc.referrer || undefined,
      utm: currentUtm(),
      ts: now()
    };
    // Only include user_id if it is a valid UUID. Non-UUID identifiers are rejected by the server.
    if (userId && isValidUUID(userId)) {
      fields.user_id = userId;
    }
    return fields;
  }

  function track(kind, opts) {
    opts = opts || {};
    if (isDisabled()) return;
    touchSession();
    var evt = baseFields();
    evt.kind = kind;
    evt.entity_type = opts.entityType || cfg.entityType;
    evt.entity_id = opts.entityId != null ? opts.entityId : cfg.entity;
    evt.surface = opts.surface || cfg.surface;
    if (opts.rail != null) evt.rail = opts.rail;
    if (opts.position != null) evt.position = opts.position;
    if (opts.dwellMs != null) evt.dwell_ms = opts.dwellMs;
    if (opts.scrollPct != null) evt.scroll_pct = opts.scrollPct;
    enqueueInteraction(evt);
    return evt;
  }

  function impression(opts) {
    opts = opts || {};
    if (isDisabled()) return;
    if (opts.entityId == null || opts.rail == null || opts.position == null) {
      warn('impression() requires entityId, rail and position');
      return;
    }
    var evt = {
      session_id: getSessionId(),
      anon_id: getAnonId(),
      surface: opts.surface || cfg.surface,
      rail: opts.rail,
      entity_id: opts.entityId,
      position: opts.position,
      ts: now()
    };
    enqueueImpression(evt);
    return evt;
  }

  // ---------------------------------------------------------------------
  // Automatic instrumentation
  // ---------------------------------------------------------------------
  function initView() {
    track('view', {});
  }

  function initScroll() {
    var ticking = false;
    function computePct() {
      var doc2 = doc.documentElement;
      var body = doc.body;
      var scrollTop = win.pageYOffset || doc2.scrollTop || (body && body.scrollTop) || 0;
      var scrollHeight = Math.max(
        (doc2 && doc2.scrollHeight) || 0,
        (body && body.scrollHeight) || 0
      );
      var clientHeight = win.innerHeight || (doc2 && doc2.clientHeight) || 0;
      var scrollable = scrollHeight - clientHeight;
      if (scrollable <= 0) return 100;
      var pct = Math.min(100, Math.round((scrollTop / scrollable) * 100));
      return pct;
    }
    function onScroll() {
      if (ticking) return;
      ticking = true;
      (win.requestAnimationFrame || win.setTimeout)(function () {
        ticking = false;
        var pct = computePct();
        if (pct > maxScrollPct) maxScrollPct = pct;
        for (var i = 0; i < SCROLL_MILESTONES.length; i++) {
          var m = SCROLL_MILESTONES[i];
          if (pct >= m && !reportedMilestones[m]) {
            reportedMilestones[m] = true;
            track('scroll', { scrollPct: m });
          }
        }
      });
    }
    win.addEventListener('scroll', safe(onScroll), { passive: true });
  }

  function initClicks() {
    function onClick(e) {
      var el = e.target;
      var depth = 0;
      while (el && el.tagName !== 'A' && depth < 8) { el = el.parentNode; depth++; }
      if (!el || el.tagName !== 'A' || !el.href) return;

      var isExternal;
      try {
        var linkHost = new win.URL(el.href, win.location.href).host;
        isExternal = linkHost && linkHost !== win.location.host;
      } catch (err) {
        isExternal = false;
      }

      var entityId = el.getAttribute('data-nowb-entity') || el.href;
      var railAttr = el.getAttribute('data-nowb-rail');
      var posAttr = el.getAttribute('data-nowb-position');

      track(isExternal ? 'outbound' : 'click', {
        entityId: entityId,
        entityType: el.getAttribute('data-nowb-entity-type') || (isExternal ? 'url' : cfg.entityType),
        rail: railAttr || undefined,
        position: posAttr != null ? parseInt(posAttr, 10) : undefined
      });
    }
    doc.addEventListener('click', safe(onClick), true);
  }

  var MAX_QUERY_LEN = 200;

  function trackSearch(q) {
    if (!q) return;
    q = String(q).slice(0, MAX_QUERY_LEN);
    // The fixed contract has no dedicated "query" field, so the search
    // term travels in entity_id with entity_type='search_query' — no new
    // fields are added to the interaction schema.
    track('search', {
      entityType: 'search_query',
      entityId: q,
      surface: 'search'
    });
  }

  function initSearch() {
    // Reports the query once per page load if the URL indicates a search
    // results page (?q=, ?s= — WordPress default) or a form is submitted.
    try {
      var params = new URLSearchParams(win.location.search || '');
      trackSearch(params.get('q') || params.get('s'));
    } catch (e) { /* ignore */ }

    doc.addEventListener('submit', safe(function (e) {
      var form = e.target;
      if (!form || !form.getAttribute) return;
      if (form.getAttribute('role') !== 'search' && !form.querySelector) return;
      var input = form.querySelector && form.querySelector('input[type="search"], input[name="s"], input[name="q"]');
      if (input && input.value) trackSearch(input.value);
    }), true);
  }

  function dwellMs() {
    return now() - pageEnteredAt;
  }

  function finalFlush() {
    if (unloading) return; // exit fires once
    unloading = true;
    if (!isDisabled()) {
      track('dwell', { dwellMs: dwellMs(), scrollPct: maxScrollPct });
      track('exit', { dwellMs: dwellMs(), scrollPct: maxScrollPct });
    }
    flush(true);
  }

  function initExit() {
    // visibilitychange fires reliably on mobile (pagehide/unload do not);
    // pagehide covers desktop back/forward-cache navigations.
    doc.addEventListener('visibilitychange', safe(function () {
      if (doc.visibilityState === 'hidden') finalFlush();
    }));
    win.addEventListener('pagehide', safe(finalFlush));
  }

  // Revoking consent must feel like a hard stop: drop anything already
  // queued (not just future calls) and cancel a pending timed flush, so
  // nothing collected a moment ago leaks out after opt-out.
  function setConsent(v) {
    runtimeConsent = v === 'granted' ? 'granted' : 'denied';
    if (runtimeConsent === 'denied') {
      interactionQueue = [];
      impressionQueue = [];
      if (flushTimer) { win.clearTimeout(flushTimer); flushTimer = null; }
    }
  }

  // ---------------------------------------------------------------------
  // Public API — window.NOWB(command, ...args) plus a couple of direct
  // methods for convenience. Kept intentionally tiny.
  // ---------------------------------------------------------------------
  var api = safe(function (cmd) {
    var args = Array.prototype.slice.call(arguments, 1);
    switch (cmd) {
      case 'consent':
        setConsent(args[0]);
        return;
      case 'identify':
        userId = args[0] || undefined;
        return;
      case 'track':
        return track(args[0], args[1]);
      case 'impression':
        return impression(args[0]);
      case 'thumbsDown':
        return track('thumbs_down', args[0]);
      case 'flush':
        return flush(false);
      default:
        warn('unknown command: ' + cmd);
    }
  });

  api.impression = safe(impression);
  api.track = safe(track);
  api.thumbsDown = safe(function (opts) { return track('thumbs_down', opts); });
  api.identify = safe(function (id) { userId = id || undefined; });
  api.consent = safe(setConsent);
  api.flush = safe(function () { flush(false); });
  api.__loaded = true;
  api.__config = cfg; // read-only convenience for debugging, not part of the contract

  // Capture any calls queued *before* this script finished loading, via:
  // <script>window.NOWB=window.NOWB||function(){(NOWB.q=NOWB.q||[]).push(arguments)}</script>
  // Must run before win.NOWB is replaced with the real api below.
  var preQueue = (win.NOWB && win.NOWB.q) || [];

  win.NOWB = api;

  for (var i = 0; i < preQueue.length; i++) {
    api.apply(null, preQueue[i]);
  }

  // ---------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------
  safe(function () {
    if (isDisabled()) return; // clean no-op: DNT or denied consent
    initView();
    initScroll();
    initClicks();
    initSearch();
    initExit();
  })();

})(window, document);
