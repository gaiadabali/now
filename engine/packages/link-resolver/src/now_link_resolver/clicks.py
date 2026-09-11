"""Click logging for paid links.

This package owns no schema and writes no migration (ticket scope), and
`engine.ad_events` (ARCHITECTURE.md Sec.5's platform DB, the append-only
invoice-basis ledger) does not exist yet -- it is E4.6, and E4.5's
`campaigns`/`placements` it references do not exist either. So this
module cannot and does not write to a ledger table; instead it defines
the **shape** a click needs to carry to be campaign-attributable later,
and a small `ClickLogger` protocol so a real sink can be plugged in
without this package needing to change:

    render (pure, no I/O) -> reader clicks the <a> -> some other consumer
    (e.g. a redirect/click endpoint the API owns, outside this package's
    scope) calls `build_click_event(...)` + `logger.log(...)`.

Rendering itself never calls a logger -- see render.py's docstring. This
keeps "idempotent and side-effect-free on render" true regardless of how
many times a page is rendered or pre-rendered.

`ClickEvent`'s fields are chosen to map cleanly onto Sec.5's
`ad_events(id, campaign_id, placement_id, session_id, kind, ts)` once
E4.6 builds it: `campaign_id`/`placement_id` are already `None`-shaped
(no campaigns exist yet -- E4.5), and `kind` is already `"click"`. The
extra fields (`partnership_id`, `org_id`, `place_id`, `site_id`,
`article_id`, `destination_url`) are exactly what E4.6 will need to fold
a link-resolver click into campaign attribution once campaigns exist;
until then they are the full attribution record on their own.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from now_link_resolver.types import LinkDecision


@dataclass(frozen=True)
class ClickEvent:
    id: str
    kind: str
    ts: datetime
    site_id: str
    article_id: str | None
    place_id: str
    org_id: str | None
    partnership_id: str | None
    destination_url: str
    session_id: str | None = None
    campaign_id: str | None = None  # E4.5 not built yet -- always None today
    placement_id: str | None = None  # E4.5 not built yet -- always None today


class ClickLogger(Protocol):
    def log(self, event: ClickEvent) -> None: ...


class InMemoryClickLogger:
    """Test/demo sink. Real persistence (into `ad_events` once E4.6 ships
    it) is deliberately not implemented here -- out of this ticket's
    scope, and the table doesn't exist to write to yet."""

    def __init__(self) -> None:
        self.events: list[ClickEvent] = []

    def log(self, event: ClickEvent) -> None:
        self.events.append(event)


def build_click_event(
    decision: LinkDecision,
    *,
    site_id: str,
    session_id: str | None = None,
    article_id: str | None = None,
) -> ClickEvent:
    """Build the attributable click record for a paid-tier decision.
    Raises on anything else -- there is nothing to log a click for on a
    free/listed link (no partner to attribute spend to)."""
    if decision.tier != "paid":
        raise ValueError(f"click logging only applies to paid-tier decisions, got tier={decision.tier!r}")
    if not decision.href:
        raise ValueError("paid decision has no href to attribute a click to")
    return ClickEvent(
        id=str(uuid.uuid4()),
        kind="click",
        ts=datetime.now(timezone.utc),
        site_id=site_id,
        article_id=article_id,
        place_id=decision.place_id,
        org_id=decision.org_id,
        partnership_id=decision.partnership_id,
        destination_url=decision.href,
        session_id=session_id,
    )
