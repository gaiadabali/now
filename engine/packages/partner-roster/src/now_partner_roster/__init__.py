"""E1.5 — Partner roster from outbound links.

Clusters the outbound-link corpus (extracted by E1.2's
`now_content_clean.links.extract_links`) into a candidate `orgs` roster for
E4 commerce, and quantifies the `rel="sponsored"`/`nofollow` SEO exposure
that feeds the E4.3 audit. See `ARCHITECTURE.md` §6 and §11.
"""

from __future__ import annotations
