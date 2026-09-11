#!/usr/bin/env node
// Zero-dependency static file server + mock /v1/{site}/events endpoint,
// used only to exercise the demo page locally. Not shipped.
'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const ROOT = path.join(__dirname, '..');
const PORT = process.env.PORT || 8933;
const LOG_FILE = path.join(__dirname, 'received-events.log.jsonl');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8'
};

fs.writeFileSync(LOG_FILE, ''); // reset each run

const server = http.createServer((req, res) => {
  const parsed = url.parse(req.url, true);

  // Mock beacon endpoint: POST /v1/{site}/events
  const eventsMatch = /^\/v1\/([^/]+)\/events\/?$/.exec(parsed.pathname);
  if (eventsMatch && req.method === 'POST') {
    let raw = '';
    req.on('data', (chunk) => { raw += chunk; });
    req.on('end', () => {
      const site = eventsMatch[1];
      const record = {
        received_at: new Date().toISOString(),
        site,
        content_type: req.headers['content-type'] || null,
        bytes: Buffer.byteLength(raw),
        body: safeParse(raw)
      };
      fs.appendFileSync(LOG_FILE, JSON.stringify(record) + '\n');
      console.log('--- events received for site=' + site + ' (' + record.bytes + ' bytes) ---');
      console.log(JSON.stringify(record.body, null, 2));
      res.writeHead(204);
      res.end();
    });
    return;
  }

  // Static files: demo/index.html, dist/beacon.min.js, src/beacon.js
  let filePath;
  if (parsed.pathname === '/' || parsed.pathname === '/index.html') {
    filePath = path.join(ROOT, 'demo', 'index.html');
  } else {
    filePath = path.join(ROOT, parsed.pathname);
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('not found: ' + parsed.pathname);
      return;
    }
    const ext = path.extname(filePath);
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
    res.end(data);
  });
});

function safeParse(raw) {
  try { return JSON.parse(raw); } catch (e) { return { __unparsed: raw }; }
}

server.listen(PORT, () => {
  console.log('Demo server: http://localhost:' + PORT + '/');
  console.log('Received events logged to: ' + LOG_FILE);
});
