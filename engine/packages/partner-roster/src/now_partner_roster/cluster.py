"""Clusters per-domain link aggregates into candidate `orgs` rows.

Two-stage clustering, both heuristic and both explained inline (per the
ticket: "a flagged unknown beats a confident error"):

1. **Domain merge** — netlocs that share a registrable root (after `www.`
   stripping, generic-subdomain stripping, a small alias table for known
   rebrands, and multi-label ccTLD suffixes like `.co.id`) become one org.
   `marriott.com` + `marriott.co.id` -> one `marriott` org.

2. **Group -> property** — a netloc with a *specific* (non-generic)
   subdomain of a root that also has its own apex cluster becomes a
   property of that group (`bali.intercontinental.com` under
   `intercontinental`). Where the group's apex domain never appears as a
   direct outbound link in this corpus, the group org is synthesized with
   zero direct link evidence and flagged so a human confirms it before it
   becomes a real `orgs` row. A second, weaker heuristic (brand-keyword
   substring match, e.g. `jwmarriottsurabaya.com` containing "marriott")
   proposes a parent for standalone domains that aren't literally
   subdomains of the group's domain — always flagged ambiguous.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from now_partner_roster.domains import (
    CANONICAL_NAMES,
    GROUP_KEYWORDS,
    ROOT_ALIASES,
    RootDomain,
    canonical_name,
    parse_root_domain,
    type_guess,
)

_WELL_KNOWN_ROOTS = set(CANONICAL_NAMES)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return s or "org"


@dataclass
class DomainAgg:
    """Everything observed for one raw netloc (e.g. "www.marriott.com")."""

    netloc: str
    link_count: int = 0
    article_ids: set[int] = field(default_factory=set)
    dates: list[str] = field(default_factory=list)  # ISO date strings
    rel_none: int = 0
    rel_nofollow: int = 0
    rel_sponsored: int = 0
    sample_articles: list[int] = field(default_factory=list)  # first N seen, in order


@dataclass
class OrgRow:
    org_slug: str
    name: str
    parent_org_slug: str | None
    domains: list[str]
    link_count: int
    article_count: int
    first_seen: str | None
    last_seen: str | None
    type_guess: str | None
    confidence: float
    sample_articles: list[int]
    rel_audit: dict[str, int]
    notes: list[str] = field(default_factory=list)
    synthesized: bool = False  # True: no direct outbound link, inferred only


@dataclass
class _ClusterKey:
    root: str
    subdomain: str | None

    def __hash__(self) -> int:
        return hash((self.root, self.subdomain))


def _resolve_root(rd: RootDomain) -> str:
    return ROOT_ALIASES.get(rd.root, rd.root)


def build_clusters(domain_aggs: dict[str, DomainAgg]) -> list[OrgRow]:
    """`domain_aggs` keyed by raw netloc (e.g. "www.marriott.com",
    "bali.intercontinental.com"). Returns one OrgRow per clustered org,
    unsorted (caller ranks by link_count)."""

    clusters: dict[_ClusterKey, list[DomainAgg]] = {}

    for netloc, agg in domain_aggs.items():
        rd = parse_root_domain(netloc)
        root = _resolve_root(rd)
        key = _ClusterKey(root=root, subdomain=rd.subdomain)
        clusters.setdefault(key, []).append(agg)

    rows: dict[str, OrgRow] = {}

    def _merge_agg(aggs: list[DomainAgg]) -> tuple[int, int, list[str] | None, list[str] | None,
                                                     dict[str, int], list[int], set[int]]:
        link_count = sum(a.link_count for a in aggs)
        article_ids: set[int] = set()
        dates: list[str] = []
        rel = {"none": 0, "nofollow": 0, "sponsored": 0}
        samples: list[int] = []
        for a in aggs:
            article_ids |= a.article_ids
            dates.extend(a.dates)
            rel["none"] += a.rel_none
            rel["nofollow"] += a.rel_nofollow
            rel["sponsored"] += a.rel_sponsored
            for s in a.sample_articles:
                if s not in samples:
                    samples.append(s)
        dates.sort()
        first_seen = dates[0] if dates else None
        last_seen = dates[-1] if dates else None
        return link_count, len(article_ids), first_seen, last_seen, rel, samples[:8], article_ids

    def _make_row(key: _ClusterKey, aggs: list[DomainAgg]) -> OrgRow:
        link_count, article_count, first_seen, last_seen, rel, samples, _ = _merge_agg(aggs)
        # strip a leading "www." for display purity per the ticket's example,
        # then dedupe (www.marriott.com + marriott.com collapse to one entry)
        # while summing link counts per bare-domain for ranking.
        bare_counts: dict[str, int] = {}
        for a in aggs:
            bare = a.netloc[4:] if a.netloc.startswith("www.") else a.netloc
            bare_counts[bare] = bare_counts.get(bare, 0) + a.link_count
        display_domains = sorted(bare_counts, key=lambda d: (-bare_counts[d], d))
        slug = slugify(key.root if key.subdomain is None else f"{key.root}-{key.subdomain}")
        name = canonical_name(key.root) if key.subdomain is None else canonical_name(key.subdomain)
        tguess, _conf_contrib = type_guess(key.root if key.subdomain is None else key.subdomain)
        base_conf = 0.9 if key.root in _WELL_KNOWN_ROOTS else 0.7
        return OrgRow(
            org_slug=slug,
            name=name,
            parent_org_slug=None,
            domains=display_domains,
            link_count=link_count,
            article_count=article_count,
            first_seen=first_seen,
            last_seen=last_seen,
            type_guess=tguess,
            confidence=base_conf,
            sample_articles=samples,
            rel_audit=rel,
            notes=[],
        )

    for key, aggs in clusters.items():
        row = _make_row(key, aggs)
        rows[row.org_slug] = row

    # --- stage 2: subdomain -> parent (group) wiring -----------------------
    # Real-evidence apex roots (a direct outbound link to the bare group
    # domain exists in this corpus) vs. synthesized ones (inferred purely
    # from a property subdomain) are tracked separately so confidence and
    # notes reflect which is which, regardless of processing order.
    real_apex_slug_for_root: dict[str, str] = {
        key.root: slugify(key.root) for key in clusters if key.subdomain is None
    }
    synthesized_slug_for_root: dict[str, str] = {}

    for key, aggs in list(clusters.items()):
        if key.subdomain is None:
            continue
        child_slug = slugify(f"{key.root}-{key.subdomain}")
        child = rows[child_slug]
        child.name = f"{canonical_name(key.root)} — {key.subdomain.replace('-', ' ').title()}"

        if key.root in real_apex_slug_for_root:
            child.parent_org_slug = real_apex_slug_for_root[key.root]
            child.confidence = min(child.confidence, 0.85)
            continue

        # synthesize the group org once per root: real evidence for the
        # property, none (yet) for the apex domain itself in this corpus.
        parent_slug = synthesized_slug_for_root.get(key.root)
        if parent_slug is None:
            parent_slug = slugify(key.root)
            rows[parent_slug] = OrgRow(
                org_slug=parent_slug,
                name=canonical_name(key.root),
                parent_org_slug=None,
                domains=[],
                link_count=0,
                article_count=0,
                first_seen=None,
                last_seen=None,
                type_guess=type_guess(key.root)[0],
                confidence=0.35,
                sample_articles=[],
                rel_audit={"none": 0, "nofollow": 0, "sponsored": 0},
                notes=[
                    "synthesized group org: no direct outbound link to this "
                    "apex domain in the corpus — inferred solely from "
                    f"subdomain propert(y/ies) such as {aggs[0].netloc}",
                ],
                synthesized=True,
            )
            synthesized_slug_for_root[key.root] = parent_slug
        child.parent_org_slug = parent_slug
        child.notes.append(
            f"parent org '{parent_slug}' synthesized — its apex domain has "
            "no direct outbound link in this corpus"
        )

    # --- stage 3: brand-keyword grandparent linking (weak, always flagged) -
    for row in list(rows.values()):
        if row.parent_org_slug is not None or row.synthesized:
            continue
        low = row.org_slug.replace("-", "")
        for kw, target_root in GROUP_KEYWORDS.items():
            target_slug = slugify(target_root)
            if target_slug == row.org_slug:
                continue
            if kw in low and target_slug in rows:
                row.parent_org_slug = target_slug
                row.confidence = min(row.confidence, 0.6)
                row.notes.append(
                    f"parent '{target_slug}' inferred from brand-keyword '{kw}' "
                    "in the domain — not a subdomain relationship; verify manually"
                )
                break

    return list(rows.values())
