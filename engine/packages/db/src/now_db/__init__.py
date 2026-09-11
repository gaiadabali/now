"""Alembic-owned `engine` schema, applied identically to every city DB.

Ownership rule (ARCHITECTURE.md §1): humans write `public` (Payload owns
it), machines write `engine` (this package owns it). `engine` can be
dropped and rebuilt from `public` at any time — nothing here is a source of
truth for editorial content, only derived/behavioural data.

This is the ONLY place city-DB DDL may be written
(`engine/packages/db/src/now_db/migrations/`). `site:create` and
`site:migrate` (see `now_db.provisioning` / `now_db.cli`) are the only
sanctioned way this DDL reaches a real database.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
