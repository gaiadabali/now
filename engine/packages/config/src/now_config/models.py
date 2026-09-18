"""Typed model of the platform `sites` registry row.

The row shape is owned by the schema agent (E0.2) and is treated here as a
fixed external contract:

    sites(id, slug, hostname, name, locale, timezone, currency,
          brand_tokens jsonb, nav jsonb, home_rails jsonb,
          ranking_weights jsonb, db_ref text, enabled_modules text[], status)

Nothing in this module, or in any consumer of `SiteConfig`, may hardcode a
site slug or hostname — see ARCHITECTURE.md §3.5. Every concrete value comes
from a registry row at runtime.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SiteStatus(str, Enum):
    """Known lifecycle states for a `sites` row.

    Treated as an open string enum: an unrecognised value coming back from
    the database is preserved rather than rejected (`use_enum_values` is not
    set), so a new status added by the schema owner never breaks the loader.
    Only ``ACTIVE`` sites are eligible to serve traffic (see
    ``SiteConfig.is_active``).
    """

    ACTIVE = "active"
    PROVISIONING = "provisioning"
    DISABLED = "disabled"


class SiteConfig(BaseModel):
    """Typed mirror of one `sites` registry row.

    Resolvable by slug or hostname via `SiteConfigLoader`. This is the only
    place request-handling code should learn anything about a specific city
    — never a literal.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: Any
    slug: str
    hostname: str
    name: str
    locale: str
    timezone: str
    currency: str
    brand_tokens: dict[str, Any] = Field(default_factory=dict)
    # `nav` and `home_rails` are ORDERED LISTS when populated, and `{}` when
    # they are not.
    #
    # Every jsonb column on `sites` is `NOT NULL DEFAULT '{}'::jsonb`, so an
    # ungoverned row holds an empty object — which is why the annotation has
    # to admit both shapes rather than just the right one. Typing these as
    # `dict` only was safe for as long as nothing wrote them; S1.3 made the
    # reader app read `nav`, and a nav is an ordered sequence of items, not a
    # mapping. A row seeded by `seed-site-registry.mjs` therefore fails
    # validation here unless `list` is allowed, and it fails at *load* time,
    # which is every request the API serves for that city.
    #
    # Nothing in Python reads either field yet; both are carried so the
    # contract stays one contract. When something does, `{}` means absent.
    nav: dict[str, Any] | list[Any] = Field(default_factory=dict)
    home_rails: dict[str, Any] | list[Any] = Field(default_factory=dict)
    ranking_weights: dict[str, Any] = Field(default_factory=dict)
    db_ref: str
    enabled_modules: list[str] = Field(default_factory=list)
    status: str

    @property
    def is_active(self) -> bool:
        return self.status == SiteStatus.ACTIVE.value

    def has_module(self, module: str) -> bool:
        return module in self.enabled_modules
