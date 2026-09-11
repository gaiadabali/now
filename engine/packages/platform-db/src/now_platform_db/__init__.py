"""Alembic-owned `engine` schema for `now_platform`.

Ownership rule (ARCHITECTURE.md §1 / §2): humans write `public`, machines
write `engine`. A Payload instance will eventually own `now_platform.public`
(sites/orgs/campaigns/placements as editorial-adjacent config) — until that
instance exists, every table this package creates lives in `now_platform.engine`
so nothing here collides with it later. This package never creates a
`public` table.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
