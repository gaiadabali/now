"""E4.2 -- the link resolution renderer (ARCHITECTURE.md Sec.11).

Articles never contain partner URLs. They contain entity references
(`<span data-place="...">`), and this package resolves each reference to
a rendered link **at render time**, from whatever partnership is
currently effective -- never from anything written into the article
itself. That is the whole commercial mechanism: a partner signing turns
every historical mention into a link instantly, and a lapsed contract
reverts at `ends_at` with no code change and no job run.
"""

from now_link_resolver.types import LinkDecision, Tier

__all__ = ["LinkDecision", "Tier"]
