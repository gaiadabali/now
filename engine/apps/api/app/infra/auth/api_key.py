"""API-key auth for beacon + widget clients, scoped per site.

Design note / follow-up for the schema owner: the `sites` row shape fixed
for E0.3 has no key column, and creating an `api_keys` table is a schema
decision that belongs to the senior-db seat, not this task. So this is an
interim, DB-free key store: keys are hashed (sha256) and configured
out-of-band via a JSON file (`Settings.api_keys_file`). Swapping it for a
DB-backed store later only means a new `ApiKeyStore` implementation --
`require_api_key` and every call site stay the same.

File shape:
    {"<site-slug>": ["<sha256-hex-of-key>", ...]}

Not yet wired to any route in this skeleton wave (no business/beacon
endpoints exist yet). E0.5 (beacon endpoint) should add
`Depends(require_api_key)` to `POST /v1/{site}/events`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from pathlib import Path as FsPath

from fastapi import Header, HTTPException, Path, Request

logger = logging.getLogger("engine_api.auth")


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class ApiKeyStore:
    def __init__(self, keys_by_site: dict[str, set[str]]) -> None:
        self._keys_by_site = keys_by_site

    @classmethod
    def from_file(cls, path: str | None) -> "ApiKeyStore":
        if not path:
            logger.warning("no api_keys_file configured; API-key auth will reject every request")
            return cls({})
        file_path = FsPath(path)
        if not file_path.exists():
            logger.warning(
                "api_keys_file %s does not exist; API-key auth will reject every request", path
            )
            return cls({})
        raw = json.loads(file_path.read_text("utf-8"))
        return cls({slug: set(hashes) for slug, hashes in raw.items()})

    def is_valid(self, site: str, raw_key: str) -> bool:
        hashes = self._keys_by_site.get(site)
        if not hashes:
            return False
        digest = hash_key(raw_key)
        return any(hmac.compare_digest(digest, stored) for stored in hashes)


async def require_api_key(
    request: Request,
    site: str = Path(..., description="City site slug."),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    """FastAPI dependency: 401s unless `X-API-Key` is valid for `site`."""
    store: ApiKeyStore = request.app.state.api_keys
    if not x_api_key or not store.is_valid(site, x_api_key):
        raise HTTPException(status_code=401, detail="missing or invalid API key")
    return x_api_key
