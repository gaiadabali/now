# F19 End-to-End Verification Guide

**Status: The beacon E2E has been verified by the orchestrator (Wave 4). This guide documents the process for re-running it.**

## Why This Matters

Migration 0003 (E0.7) changed the server from accepting base36 IDs to requiring RFC4122 UUIDs. The beacon now emits UUIDs (fixed in F19), and **end-to-end verification proves the server accepts them**. Unit tests alone cannot prove server compatibility — there could easily be a second format mismatch behind the first one (E0.5 already discovered this once).

## Prerequisites

Ensure the following are running:
- Postgres on `localhost:15432` with database `now_jakarta` (or read from project `.env`)
  - Credentials: loaded from project `.env` file (or overridden via `ENGINE_API_CITY_DB_*` env vars)
- Redis on `localhost:16379` (or read from project `.env`)
- The API server running from `engine/apps/api`

## Verification Steps

### 1. Start the API Server

The API reads `ENGINE_API_*` environment variables, and also respects the project's `.env` file. For local testing with the remapped ports, use:

```bash
cd engine/apps/api
# Option A: Let the API read from project .env automatically
uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level debug

# Option B: Override specific settings (if needed)
ENGINE_API_CITY_DB_HOST=localhost ENGINE_API_CITY_DB_PORT=15432 ENGINE_API_CITY_DB_PASSWORD="$POSTGRES_PASSWORD" \
  uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level debug
```

### 2. Serve the Beacon Demo

In another terminal:
```bash
cd engine/packages/beacon/demo
node server.js
```

The demo should be accessible at `http://localhost:8933/`

### 3. Generate Events Through the Beacon

Open `http://localhost:8933/` in a browser and interact with the demo page. The page includes buttons to test:
- `view` event (automatic on load)
- `click` and `outbound` events (click buttons)
- `scroll` events (scroll the page)
- `search` events (submit the form)
- `impression` events (via explicit API calls)

Watch the terminal running `demo/server.js` — it logs all events received.

### 4. Verify HTTP Status Codes

**Critical:** Check that the API returns 2xx status codes, not 4xx.

The `demo/server.js` logs will show something like:
```
POST /v1/test/events 200 OK
POST /v1/test/events 200 OK
```

If you see 400/422/4xx, the beacon is being rejected (the whole point of F19 is that this should NOT happen now).

### 5. Query Postgres for the Results

Connect to the database and verify rows were written with valid UUIDs:

```bash
psql -h localhost -p 15432 -U now -d now_jakarta
```

Then run:

```sql
SELECT 
  anon_id, 
  session_id, 
  user_id,
  kind, 
  entity_type, 
  entity_id, 
  target_url, 
  query,
  ts 
FROM engine.interactions 
ORDER BY ts DESC 
LIMIT 20;
```

**Expected results:**
- `anon_id` and `session_id` are valid RFC4122 UUIDs (format: `8-4-4-4-12` hex digits with hyphens)
- Example: `550e8400-e29b-41d4-a716-446655440000`
- `user_id` is NULL (unless you called `NOWB('identify', valid_uuid)` with a valid UUID)
- `kind` shows: `view`, `click`, `outbound`, `scroll`, `search`, `dwell`, `exit` ✓
- `entity_type` varies: `article`, `url` (for outbound), `search_query` (for search) ✓
- No server-side errors or 4xx responses in the logs

### 6. Test at Least These Event Types

Exercise the beacon to generate:
- [ ] `view` (automatic)
- [ ] `scroll` (scroll to 25%, 50%, 75%, 100%)
- [ ] `search` (submit the search form)
- [ ] `outbound` (click an external link)
- [ ] `click` (click an internal link)
- [ ] `impression` (via `NOWB('impression', {...})`)

All should result in 200 responses and rows in Postgres with valid UUIDs.

## Success Criteria

✅ All HTTP responses are 2xx (no 4xx errors)  
✅ All rows in `engine.interactions` have valid RFC4122 UUIDs for `anon_id` and `session_id`  
✅ All event kinds (view, click, outbound, scroll, search, exit, dwell) are present  
✅ `user_id` is NULL when not set via `identify()`, or a UUID when set to one  
✅ No changes needed to the beacon or server payload contract  

## If It Fails

- **4xx errors in logs**: The server is still rejecting the UUIDs. Check that migration 0003 is applied and the server is restarted.
- **Invalid UUID format**: The beacon code has a bug in `generateUUID()` or the fallback. Review the beacon source.
- **Mismatch between unit tests and E2E**: Document the discrepancy — there's a real bug somewhere.

## Notes for Future Runs

This process mirrors E0.5's verification (see PROGRESS.md Wave 2). If you need to re-run it:
- The beacon demo server (`demo/server.js`) logs all requests with status codes
- Postgres queries show what actually persisted
- Combination of the two proves end-to-end correctness
