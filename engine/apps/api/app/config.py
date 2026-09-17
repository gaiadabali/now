"""Process-wide settings for engine-api.

Everything that differs *per city* lives in the `sites` registry row and is
loaded through `now_config.SiteConfig` — never here. This module only holds
things that are the same for every tenant: how to reach the platform
database, how to build a city DSN from a `db_ref`, cache TTLs, and the
optional Redis rate-limit backend.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ENGINE_API_", env_file=".env", extra="ignore")

    env: str = "development"
    log_level: str = "INFO"

    # --- Extra beacon origins, per site ------------------------------------
    # `ENGINE_API_EXTRA_ALLOWED_ORIGINS={"jakarta":["https://now-jakarta.example"]}`
    #
    # The events allowlist is built from `sites.hostname` (decision C2), which
    # holds the site's *canonical* hostname. That is not always where the site
    # is being served: during a pre-cutover phase the engine runs on a staging
    # domain while `hostname` still names the domain the legacy site occupies.
    # When those differ, every beacon batch is rejected 403 — the site's own
    # origin judged exactly like a hostile one — and nothing is collected.
    # That is what happened in production and it cost a week, because the 403
    # never said which origin had been refused.
    #
    # Deliberately NOT "just change `sites.hostname`": that column also drives
    # `metadataBase` in the reader app, so moving it would drag canonical and
    # OG URLs onto the staging domain. `hostname` stays the post-cutover truth
    # and this names where the site is served *today*. After a cutover the
    # entry becomes redundant and can be deleted, which is the property that
    # makes this the right shape rather than a permanent parallel config.
    #
    # Keyed by site slug, never a flat list: a flat list would let one city's
    # origin write behaviour into another city's database, which is the
    # boundary the per-site check exists to hold.
    #
    # A dict of lists, so pydantic-settings parses the JSON itself. Hand-rolled
    # "slug:origin,slug:origin" parsing would be one more thing to get subtly
    # wrong for no gain.
    extra_allowed_origins: dict[str, list[str]] = {}

    # --- Platform DB (single shared pool) ---------------------------------
    platform_database_url: str = (
        "postgresql+asyncpg://now:now@localhost:5432/now_platform"
    )
    platform_pool_size: int = 5
    platform_pool_max_overflow: int = 5

    # --- City DB pool construction -----------------------------------------
    # `sites.db_ref` is a free-form `text` column owned by the schema agent
    # (E0.2). Two shapes are supported with zero code change either way:
    #
    #   1. A full async DSN:      "postgresql+asyncpg://user:pass@host:5432/now_bandung"
    #   2. A bare database name:  "now_bandung"
    #
    # Case 2 is expected to be the common one — ARCHITECTURE.md §2 puts every
    # city on the *same* Postgres 16 instance, so only the database name
    # varies per site. The shared connection template below supplies the
    # rest. This is a documented assumption, not a hardcoded site: adding a
    # city only ever means inserting a registry row.
    city_db_host: str = "localhost"
    city_db_port: int = 5432
    city_db_user: str = "now"
    city_db_password: str = "now"
    city_db_sslmode: str | None = None
    city_pool_size: int = 5
    city_pool_max_overflow: int = 5
    # Seconds a lazily-created, unused city pool is kept alive before being
    # disposed. 0 disables idle eviction.
    city_pool_idle_ttl_seconds: int = 0

    def build_city_dsn(self, db_ref: str) -> str:
        if "://" in db_ref:
            return db_ref
        dsn = (
            f"postgresql+asyncpg://{self.city_db_user}:{self.city_db_password}"
            f"@{self.city_db_host}:{self.city_db_port}/{db_ref}"
        )
        return dsn

    # --- Site registry cache -------------------------------------------------
    site_registry_cache_ttl_seconds: float = 30.0

    # --- Auth / rate limiting -------------------------------------------------
    # JSON map of site slug -> list of accepted API key hashes (sha256 hex).
    # Interim, DB-free key store — see app/infra/auth/api_key.py docstring.
    api_keys_file: str | None = None
    redis_url: str | None = "redis://localhost:6379/0"
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
