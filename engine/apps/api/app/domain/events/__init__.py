"""Events (interaction beacon) domain -- E0.5.

`POST /v1/{site}/events` lands here: validates and writes beacon batches
(view/scroll/dwell/click/outbound/search/exit/thumbs_down interactions, plus
rail impressions) into `engine.interactions` / `engine.impressions`.

Auth note (open contract decision C2, PROGRESS.md): ARCHITECTURE.md
§16/E0.3's README describe `Depends(require_api_key)` for this endpoint --
that has been superseded. A key shipped inside public client JS on a public
website is not a secret, so this endpoint does **not** use API-key auth.
Instead: a CORS origin allowlist derived from the site registry's
`hostname` (see `app/api/v1/events.py`) and rate limiting keyed by the
beacon's `anon_id` (see `app/domain/events/service.py`). Real API keys are
reserved for server-to-server consumers (C3), which this endpoint is not.

Uses `Depends(get_city_db)` from `app.infra.db.deps`. See
`engine/apps/api/README.md` and `engine/packages/beacon/README.md` for the
exact wire contract.
"""
