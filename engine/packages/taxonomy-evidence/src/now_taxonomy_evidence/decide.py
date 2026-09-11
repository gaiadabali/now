"""Assemble the evidence pack: per-category records, statuses, the decision
registry with computed evidence, cross-city consistency, calibration.

One in-memory model per city plus a shared block (decisions, vocabulary,
cross-city). Both renderers (Markdown, JSON) consume exactly this model --
they cannot drift because neither computes anything.
"""
from __future__ import annotations

import copy
import random
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np

from . import coherence as coh
from .lexicons import CANDIDATES
from .proposals import BALI_PROPOSALS, CONTAINERS, DECISIONS, JAKARTA_ADJUSTMENTS
from .resolutions import CATEGORY_RESOLUTIONS, DECIDED_BY, DECIDED_ON, EVIDENCE_FLAG_POLICY, RESOLUTIONS, RULES
from .sources import HOME_LOCATION, Article, Category
from .text import DECAY_CLASS, FORMATS, TYPES, VENUE_TYPES
from .vectors import VectorSpace

TOOL_VERSION = "0.2.0"  # 0.1.0 = E2.0 evidence pack; 0.2.0 = resolved (Hansel's 27 answers applied)
SAMPLE_N = 8
LLM_TITLES = 20
PER_ARTICLE_ORDER = ("type", "subtype", "format", "location")

_END_DATE = re.compile(r"\b(valid (until|through|till|from)|available (until|through|from)|until \d|through \d|from \d{1,2} (january|february|march|april|may|june|july|august|september|october|november|december|\w+ (to|until|-)))", re.I)
_NON_ARTICLE = re.compile(r"\b(order form|purchas(e|ing)|subscri(be|ption)|magazine[s]? (order|subscription)|national day|advertis(e|ing) with)\b", re.I)


def _spread(items: list, k: int) -> list:
    n = len(items)
    if n <= k:
        return list(items)
    idx = sorted({int(round(i * (n - 1) / (k - 1))) for i in range(k)})
    return [items[i] for i in idx]


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def _dist(counter: Counter, n: int) -> dict:
    """{value: share} over signal-bearing articles + coverage."""
    signal = {k: v for k, v in counter.items() if k is not None}
    total = sum(signal.values())
    dist = {k: round(v / total, 3) for k, v in sorted(signal.items(), key=lambda kv: -kv[1])} if total else {}
    return {"dist": dist, "coverage": round(total / n, 3) if n else 0.0, "n_signal": total}


def _top(dist: dict) -> tuple[str | None, float]:
    if not dist:
        return None, 0.0
    k = next(iter(dist))
    return k, dist[k]


class CityBuild:
    def __init__(self, city: str, articles: list[Article], cats: dict[str, Category], features: dict[int, dict], space: VectorSpace,
                 seed: dict, e14: dict[str, dict] | None):
        self.city = city
        self.articles = articles
        self.cats = cats
        self.features = features
        self.space = space
        self.seed = seed
        self.e14 = e14 or {}
        self.home = HOME_LOCATION[city]
        self.members: dict[str, list[Article]] = defaultdict(list)
        for a in articles:
            for c in set(a.categories):
                self.members[c].append(a)
        for c in self.members.values():
            c.sort(key=lambda a: a.date)
        self.by_id = {a.wp_id: a for a in articles}
        self.term_to_name = {c.term_id: c.name for c in cats.values() if c.term_id is not None}
        # location slug -> city root
        self.loc_root: dict[str, str] = {}
        for t in seed["terms"]["location"]:
            p = t["path"]
            self.loc_root[t["slug"]] = p[1] if len(p) > 1 and p[0] == "indonesia" else p[0]
        self.records: dict[str, dict] = {}
        self.coherence: dict[str, coh.Coherence] = {}

    # ---- proposals ---------------------------------------------------------
    def proposal_for(self, name: str) -> dict:
        if self.city == "bali":
            p = BALI_PROPOSALS.get(name)
            if p is None:
                return {"type": None, "subtype": None, "format": None, "location": self.home, "per_article": ["type", "subtype", "format"], "facets": {},
                        "series_key": None, "kind": "editorial", "confidence": "low", "decisions": [], "reasoning": "No proposal authored -- category not seen when the pack was written.",
                        "alternates": [], "container": False, "auto": False, "source": "none"}
            out = dict(p)
            out["source"] = "evidence-pack proposal (Bali has no E1.4 draft)"
            return out
        e = self.e14.get(name)
        if e is None:
            return {"type": None, "subtype": None, "format": None, "location": self.home, "per_article": ["type", "subtype", "format"], "facets": {},
                    "series_key": None, "kind": "editorial", "confidence": "low", "decisions": [], "reasoning": "Not in E1.4's draft.", "alternates": [], "container": False, "auto": False, "source": "none"}
        prior = e.get("prior") or {}
        out = {
            "type": prior.get("type"), "subtype": prior.get("subtype"), "format": prior.get("format"), "location": prior.get("location"),
            "per_article": list(e.get("per_article") or []), "facets": dict(prior.get("facets") or {}), "series_key": e.get("series_key"),
            "kind": "print-issue" if e.get("is_print_issue") else "editorial", "confidence": e.get("confidence", "low"),
            "decisions": ["D07"] if e.get("is_print_issue") else [], "reasoning": e.get("notes") or "", "alternates": list(e.get("alternates") or []),
            "container": name in CONTAINERS["jakarta"], "auto": not bool(e.get("decision_needed")), "source": "E1.4 draft (carried)",
            "e14_decision": e.get("decision"),
        }
        adj = JAKARTA_ADJUSTMENTS.get(name)
        if adj:
            out["decisions"] = list(adj.get("decisions", out["decisions"]))
            out["auto"] = adj.get("auto", out["auto"])
            for k in ("type", "subtype", "format", "location", "per_article"):
                if k in adj:
                    out[k] = adj[k]
            if adj.get("note"):
                out["reasoning"] = (adj["note"] + " | E1.4: " + out["reasoning"]).strip(" |")
                out["source"] = "E1.4 draft, amended by the evidence pack" if any(k in adj for k in ("type", "subtype", "format", "per_article")) else out["source"]
        if e.get("is_print_issue"):
            out["auto"] = True
        return out

    # ---- per-category evidence -------------------------------------------
    def build_records(self) -> None:
        cooc = defaultdict(Counter)
        for a in self.articles:
            cs = sorted(set(a.categories))
            for i, x in enumerate(cs):
                for y in cs[i + 1:]:
                    cooc[x][y] += 1
                    cooc[y][x] += 1
        for name, cat in self.cats.items():
            members = self.members.get(name, [])
            n = len(members)
            prop = self.proposal_for(name)
            feats = [self.features.get(a.wp_id, {}) for a in members]
            type_c = Counter(f.get("type") for f in feats)
            fmt_c = Counter(f.get("format") for f in feats)
            stamped = sum(1 for f in feats if f.get("period_stamp"))
            roundup = sum(1 for f in feats if f.get("roundup"))
            fp = [f.get("fp_density", 0.0) for f in feats if f]
            loc_c: Counter = Counter()
            outside = 0
            for f in feats:
                slugs = f.get("locations") or []
                roots = {self.loc_root.get(s, s) for s in slugs}
                for s in slugs:
                    loc_c[s] += 1
                if roots and self.home not in roots and not any(self.loc_root.get(s) == self.home for s in slugs):
                    outside += 1
            samples = [{"wp_id": a.wp_id, "date": a.date[:10], "title": a.title} for a in _spread(members, SAMPLE_N)]
            self.records[name] = {
                "name": name, "slug": cat.slug, "term_id": cat.term_id, "parent": cat.parent_name, "description": cat.description, "city": self.city,
                "published": n, "wp_count": cat.wp_count, "first_year": cat.first_year, "last_year": cat.last_year,
                "years": {str(k): v for k, v in sorted(cat.years.items())}, "yoast_primary": cat.yoast_primary,
                "cooccurs": [{"category": c, "articles": k} for c, k in cooc[name].most_common(3)],
                "single_category_articles": sum(1 for a in members if len(set(a.categories)) == 1),
                "proposal": {k: prop.get(k) for k in ("type", "subtype", "format", "location", "per_article", "facets", "series_key")},
                "kind": prop.get("kind", "editorial"), "container": bool(prop.get("container")), "confidence": prop.get("confidence", "low"),
                "reasoning": prop.get("reasoning", ""), "alternates": prop.get("alternates", []), "proposal_source": prop.get("source"),
                "e14": self.e14.get(name) and {k: self.e14[name].get(k) for k in ("confidence", "decision_needed", "decision", "prior", "per_article", "alternates", "series_key", "notes")},
                "decisions": list(prop.get("decisions", [])), "auto_proposed": bool(prop.get("auto", False)),
                "samples": samples,
                "cues": {"type": _dist(type_c, n), "format": _dist(fmt_c, n)},
                "period_stamped_share": round(stamped / n, 3) if n else 0.0, "roundup_share": round(roundup / n, 3) if n else 0.0,
                "fp_density_median": round(statistics.median(fp), 1) if fp else 0.0,
                "locations": {"top": [{"slug": s, "articles": k} for s, k in loc_c.most_common(6)], "outside_home_share": round(outside / n, 3) if n else 0.0},
                "coherence": None, "llm": None, "flags": [], "status": None,
            }

    # ---- coherence ---------------------------------------------------------
    def run_coherence(self) -> None:
        if not self.space.matrix.size:
            return
        curve = coh.baseline_curve(self.space)
        centroids = coh.category_centroids(self.space, self.members)
        rng = random.Random(0)
        fixed_type_of = {n: (r["proposal"]["type"] if "type" not in r["proposal"]["per_article"] else None) for n, r in self.records.items()}
        for name, rec in self.records.items():
            members = self.members.get(name, [])
            prop = rec["proposal"]
            expected = ("type" in prop["per_article"]) or rec["container"] or rec["kind"] == "print-issue"
            res = coh.analyse_category(name, members, self.space, centroids, self.features, {len(members): coh.baseline_for(len(members), curve)},
                                       expected, prop["type"] if "type" not in prop["per_article"] else None,
                                       prop["format"] if "format" not in prop["per_article"] else None, rng, fixed_type_of)
            self.coherence[name] = res
            rec["coherence"] = res.to_dict()

    # ---- status ------------------------------------------------------------
    def assign_status(self) -> None:
        for name, rec in self.records.items():
            flags: list[str] = []
            prop = rec["proposal"]
            n = rec["published"]
            if n == 0:
                rec["status"] = "empty"
                rec["flags"] = []
                continue
            tcue = rec["cues"]["type"]
            fcue = rec["cues"]["format"]
            print_issue = rec["kind"] == "print-issue"
            # Type: only a disagreement that crosses into (or between) venue types
            # can change competitor exclusion; editorial<->do<->event never excludes.
            if prop["type"] and "type" not in prop["per_article"] and n >= 10 and tcue["coverage"] >= 0.4 and not print_issue:
                share = tcue["dist"].get(prop["type"], 0.0)
                top, top_share = _top(tcue["dist"])
                crosses_venue = (top in VENUE_TYPES or prop["type"] in VENUE_TYPES)
                if share <= 0.3 and top != prop["type"] and top_share >= 0.5 and crosses_venue:
                    flags.append(f"cue instrument disagrees on type: proposal fixes `{prop['type']}` but {_pct(top_share)} of signal-bearing articles read as `{top}` (only {_pct(share)} as `{prop['type']}`) -- this changes competitor exclusion")
            # Format: only a disagreement across decay classes matters; `feature` has no
            # lexical cue of its own, so it is never contradicted by the instrument.
            if prop["format"] and prop["format"] != "feature" and "format" not in prop["per_article"] and n >= 10 and fcue["coverage"] >= 0.4 and not print_issue:
                share = fcue["dist"].get(prop["format"], 0.0)
                top, top_share = _top(fcue["dist"])
                if share <= 0.3 and top != prop["format"] and top_share >= 0.5 and DECAY_CLASS.get(top) != DECAY_CLASS.get(prop["format"]):
                    flags.append(f"cue instrument disagrees on format: proposal fixes `{prop['format']}` ({DECAY_CLASS.get(prop['format'])} decay) but {_pct(top_share)} of signal-bearing articles read as `{top}` ({DECAY_CLASS.get(top)} decay; only {_pct(share)} as `{prop['format']}`)")
            c = rec["coherence"]
            if c and c["verdict"] == "incoherent" and not print_issue:
                flags.append(f"clusters split the category: {c['reason']}")
            llm = rec["llm"]
            if llm and llm.get("result") and not print_issue:
                r = llm["result"]
                lt, lf = r.get("type"), r.get("format")
                if prop["type"] and "type" not in prop["per_article"] and lt and lt != "per-article" and lt in TYPES and lt != prop["type"] and (lt in VENUE_TYPES or prop["type"] in VENUE_TYPES):
                    flags.append(f"LLM second opinion reads type as `{lt}` (proposal `{prop['type']}`): {r.get('rationale', '')}")
                if prop["format"] and "format" not in prop["per_article"] and lf and lf != "per-article" and lf in FORMATS and lf != prop["format"] and r.get("confidence") == "high" and DECAY_CLASS.get(lf) != DECAY_CLASS.get(prop["format"]):
                    flags.append(f"LLM second opinion reads format as `{lf}` ({DECAY_CLASS.get(lf)} decay; proposal `{prop['format']}` is {DECAY_CLASS.get(prop['format'])}): {r.get('rationale', '')}")
            rec["flags"] = flags
            vocab_only = rec["decisions"] and all(_decision_kind(d) in ("vocabulary",) for d in rec["decisions"])
            if not rec["auto_proposed"]:
                rec["status"] = "decision-needed"
            elif flags:
                rec["status"] = "flagged-by-evidence"
            elif rec["kind"] == "print-issue":
                rec["status"] = "auto-accepted (print issue, D07)"
            elif vocab_only:
                rec["status"] = "auto-accepted (pending vocabulary sign-off)"
            elif rec["decisions"]:
                rec["status"] = "auto-accepted (policy decisions apply)"
            else:
                rec["status"] = "auto-accepted"

    # ---- resolution (Hansel's answers, 2026-09-10) -------------------------
    def apply_resolutions(self) -> None:
        """Apply `resolutions.py` on top of the E2.0 proposal. Runs AFTER the
        evidence phase (features, coherence, LLM, flags), so every instrument
        reading stays exactly what the decisions were made against; the
        pre-resolution proposal and status are kept as `e20_proposal` /
        `e20_status`. Fails loudly if an answer names an unknown category or
        decision, or leaves an evidence flag unaddressed -- a wrong table must
        not produce a quietly half-resolved pack."""
        overrides = CATEGORY_RESOLUTIONS.get(self.city, {})
        unknown = set(overrides) - set(self.records)
        if unknown:
            raise KeyError(f"{self.city}: CATEGORY_RESOLUTIONS names categories that do not exist: {sorted(unknown)}")
        unaddressed: list[str] = []
        for name, rec in self.records.items():
            rec["e20_proposal"] = copy.deepcopy(rec["proposal"])
            rec["e20_status"] = rec["status"]
            if rec["status"] == "empty":
                rec["resolution"] = {"status": "empty", "changed": False, "changes": {}, "basis": [], "note": "no published articles; nothing to map",
                                     "addressed_flags": [], "decided_by": DECIDED_BY, "decided_on": DECIDED_ON}
                continue
            ov = overrides.get(name, {})
            p = rec["proposal"]
            changes: dict = {}
            for k in ("type", "subtype", "format", "location"):
                if k in ov and ov[k] != p.get(k):
                    changes[k] = {"from": p.get(k), "to": ov[k]}
                    p[k] = ov[k]
            if ov.get("per_article"):
                wanted = set(p["per_article"]) | set(ov["per_article"])
                new = [k for k in PER_ARTICLE_ORDER if k in wanted]
                if new != list(p["per_article"]):
                    changes["per_article"] = {"from": list(p["per_article"]), "to": new}
                    p["per_article"] = new
            if "facets" in ov:
                merged = dict(p.get("facets") or {})
                for fk, fv in ov["facets"].items():
                    if merged.get(fk) != list(fv):
                        changes.setdefault("facets", {})[fk] = {"from": merged.get(fk), "to": list(fv)}
                        merged[fk] = list(fv)
                p["facets"] = merged
            if ov.get("alternates_prepend"):
                rec["alternates"] = list(ov["alternates_prepend"]) + [a for a in rec["alternates"] if a not in ov["alternates_prepend"]]
            for d in ov.get("decisions_add", []):
                if d not in rec["decisions"]:
                    rec["decisions"].append(d)
            basis = list(ov.get("basis") or rec["decisions"] or ["as-proposed"])
            for b in [*basis, *rec["decisions"]]:
                if b not in ("as-proposed", EVIDENCE_FLAG_POLICY["id"]) and b not in RESOLUTIONS:
                    raise KeyError(f"{self.city}/{name}: basis or decision {b!r} has no entry in RESOLUTIONS")
            if rec["flags"] and not ov:
                unaddressed.append(name)
            rec["resolution"] = {
                "status": "resolved", "changed": bool(changes), "changes": changes, "basis": basis, "note": ov.get("note", ""),
                "addressed_flags": list(rec["flags"]) if ov else [],
                "decided_by": DECIDED_BY, "decided_on": DECIDED_ON,
            }
            if rec["kind"] == "print-issue":
                rec["status"] = "resolved (print issue, D07)"
            elif changes:
                rec["status"] = f"resolved — changed ({', '.join(basis)})"
            elif basis == ["as-proposed"]:
                rec["status"] = "resolved (as proposed)"
            else:
                rec["status"] = f"resolved ({', '.join(basis)})"
        if unaddressed:
            raise RuntimeError(f"{self.city}: evidence flags left unaddressed by CATEGORY_RESOLUTIONS: {unaddressed}")


_DECISION_KIND = {d["id"]: d["kind"] for d in DECISIONS}


def _decision_kind(did: str) -> str:
    return _DECISION_KIND.get(did, "mapping")


# ---------------------------------------------------------------------------
# cross-city assembly
# ---------------------------------------------------------------------------

def _norm(name: str) -> str:
    n = name.lower().replace("&", "and").replace("!", "").strip()
    n = re.sub(r"\s+", " ", n)
    if n.endswith("guides"):
        n = n[:-1]
    return n


def cross_city(builds: dict[str, CityBuild]) -> list[dict]:
    if len(builds) < 2:
        return []
    j, b = builds["jakarta"], builds["bali"]
    jn = {_norm(n): n for n in j.records}
    bn = {_norm(n): n for n in b.records}
    out = []
    for key in sorted(set(jn) & set(bn)):
        rj, rb = j.records[jn[key]], b.records[bn[key]]
        pj, pb = rj["proposal"], rb["proposal"]

        def eff(p, k):
            return "per-article" if k in p["per_article"] or p[k] is None else p[k]

        def compare(k):
            a, b_ = eff(pj, k), eff(pb, k)
            if a == b_:
                return "same", None
            if "per-article" in (a, b_):
                side = "jakarta" if a == "per-article" else "bali"
                return "partial", f"{k}: {side} leaves it per article (evidence-based), the other fixes `{a if side == 'bali' else b_}`"
            return "conflict", f"{k}: jakarta `{a}` vs bali `{b_}`"
        st, notes = zip(compare("type"), compare("format"))
        verdict = "conflict" if "conflict" in st else ("partial" if "partial" in st else "same")
        out.append({
            "category": key, "jakarta": {"name": jn[key], "articles": rj["published"], "type": eff(pj, "type"), "format": eff(pj, "format"), "status": rj["status"]},
            "bali": {"name": bn[key], "articles": rb["published"], "type": eff(pb, "type"), "format": eff(pb, "format"), "status": rb["status"]},
            "consistent": verdict == "same", "verdict": verdict,
            "note": "; ".join(n for n in notes if n),
        })
    return out


def calibration(builds: dict[str, CityBuild]) -> list[dict]:
    """How well the cue instrument agrees with categories nobody disputes."""
    rows = []
    undisputed = {
        "jakarta": {"Dining Offers": ("eat", "offer"), "Stay Offers": ("stay", "offer"), "Reviews": ("eat", "review"), "Dining News": ("eat", "news"), "Events": ("event", "event"),
                    "Bar Guide": ("drink", None), "Music": ("event", "event"), "Education": ("editorial", None), "NOW! People": ("editorial", "people"), "History & Heritage": ("editorial", "heritage"),
                    "Opinion": ("editorial", "opinion"), "World Traveller": (None, "city-guide")},
        "bali": {"Dining Offers": ("eat", "offer"), "Stay Offers": ("stay", "offer"), "Reviews": ("eat", "review"), "Spa and Wellness": ("wellness", None), "Hotels & Resorts": ("stay", None),
                 "Restaurants and Bars": ("eat", None), "Bar Guide": ("drink", None), "Opinion": ("editorial", "opinion"), "Dining News": ("eat", "news"), "Activities": ("do", None), "People of Bali": ("editorial", "people"), "Bali History": ("editorial", "heritage")},
    }
    for city, table in undisputed.items():
        bld = builds.get(city)
        if not bld:
            continue
        for name, (t, f) in table.items():
            rec = bld.records.get(name)
            if not rec:
                continue
            rows.append({"city": city, "category": name, "n": rec["published"],
                         "type": t, "type_share": rec["cues"]["type"]["dist"].get(t) if t else None, "type_coverage": rec["cues"]["type"]["coverage"],
                         "format": f, "format_share": rec["cues"]["format"]["dist"].get(f) if f else None, "format_coverage": rec["cues"]["format"]["coverage"]})
    return rows


def _members_in(bld: CityBuild, name: str) -> list[Article]:
    return bld.members.get(name, [])


def decision_evidence(builds: dict[str, CityBuild], vocab: dict) -> list[dict]:
    """Attach computed evidence and affected categories to every registry decision."""
    out = []
    j, b = builds.get("jakarta"), builds.get("bali")

    def rec(city, name):
        bld = builds.get(city)
        return bld.records.get(name) if bld else None

    def cue_line(city, name):
        r = rec(city, name)
        if not r:
            return None
        t = ", ".join(f"{k} {_pct(v)}" for k, v in list(r["cues"]["type"]["dist"].items())[:4])
        f = ", ".join(f"{k} {_pct(v)}" for k, v in list(r["cues"]["format"]["dist"].items())[:4])
        return f"{city} '{name}' ({r['published']}): type cues {t or 'none'} (coverage {_pct(r['cues']['type']['coverage'])}); format cues {f or 'none'} (coverage {_pct(r['cues']['format']['coverage'])})"

    def cluster_line(city, name):
        r = rec(city, name)
        if not r or not r.get("coherence") or not r["coherence"].get("clusters"):
            return None
        c = r["coherence"]
        parts = []
        for cl in c["clusters"]:
            ex = "; ".join(e["title"][:60] for e in cl["examples"][:2])
            parts.append(f"{_pct(cl['share'])} [{cl['top_type'] or '?'}/{cl['top_format'] or '?'}] e.g. {ex}")
        return f"{city} '{name}' clusters ({c['vector_source'].split(' ')[0]}, k={c['best_k']}, silhouette {c['silhouette']}): " + " | ".join(parts)

    cand = {r["key"]: r for r in vocab.get("candidates", [])}
    seed_terms = {r["key"]: r for r in vocab.get("seed_terms", [])}
    all_cands = {r["key"]: r for r in vocab.get("_all_candidates", [])}

    def cand_total(key):
        r = cand.get(key) or all_cands.get(key)
        return r["total"] if r else 0

    for d in DECISIONS:
        did = d["id"]
        ev: list[str] = []
        affects = []
        for city, bld in builds.items():
            for name, r in bld.records.items():
                if did in r["decisions"]:
                    affects.append({"city": city, "category": name, "articles": r["published"]})
        affects.sort(key=lambda x: -x["articles"])
        total = sum(a["articles"] for a in affects)

        if did == "D01":
            for city, bld in builds.items():
                for name in ("Bar Guide", "Restaurant Guides", "Restaurant Guide", "City Guides", "Dining", "Bali with Kids", "Weddings"):
                    r = bld.records.get(name)
                    if r and r["published"]:
                        ev.append(f"{city} '{name}': {_pct(r['period_stamped_share'])} of titles carry a period stamp (year / [Updated] / season), {_pct(r['roundup_share'])} are roundups; {r['first_year']}-{r['last_year']}")
        elif did == "D02":
            for city, bld in builds.items():
                offers = [a for n in ("Dining Offers", "Stay Offers", "Experience Offers", "Offers") for a in _members_in(bld, n)]
                seen = {}
                for a in offers:
                    seen[a.wp_id] = a
                offers = list(seen.values())
                if offers:
                    dead = sum(1 for a in offers if a.year <= 2023)
                    dated = sum(1 for a in offers if _END_DATE.search(a.text))
                    ev.append(f"{city}: {len(offers)} offer-category articles; {_pct(dead / len(offers))} published 2023 or earlier (certainly expired); {_pct(dated / len(offers))} carry an explicit validity phrase the extractor can read")
                events = _members_in(bld, "Events")
                if events:
                    dead = sum(1 for a in events if a.year <= 2023)
                    ev.append(f"{city}: {len(events)} Events; {_pct(dead / len(events))} from 2023 or earlier")
        elif did == "D03":
            for city, bld in builds.items():
                r = bld.records.get("Opinion")
                nr = bld.records.get("News")
                if r and nr:
                    ev.append(f"{city} Opinion ({r['published']}, {r['first_year']}-{r['last_year']}): median first-person density {r['fp_density_median']}/1000 words vs News {nr['fp_density_median']} -- columns, not reportage; {_pct(sum(v for y, v in r['years'].items() if int(y) <= 2020) / r['published'])} are from 2020 or earlier and would stay evergreen as `feature`")
        elif did in ("D04", "D05", "D11", "D12", "D13", "D24"):
            ev.append(f"{len(affects)} categories / {total} articles depend on this approval: " + ", ".join(f"{a['city']}:{a['category']} ({a['articles']})" for a in affects[:12]) + (" ..." if len(affects) > 12 else ""))
            if did == "D13":
                ev.append(f"corpus mentions -- retreat: {cand_total('venue_kind/Retreat centre') + cand_total('occasion/Retreat')} articles; salon/barbershop/nail: {cand_total('venue_kind/Barbershop') + cand_total('venue_kind/Nail bar')}; yoga studio: {cand_total('venue_kind/Yoga studio')} (lexical counts, see vocabulary section)")
            if did == "D11":
                ev.append(f"corpus mentions -- golf course/club: {cand_total('venue_kind/Golf course')}; padel/tennis: {cand_total('venue_kind/Padel / tennis')}; climbing: {cand_total('venue_kind/Climbing gym')}; running club: {cand_total('venue_kind/Running club')}")
        elif did == "D06":
            intl = [r for r in vocab.get("candidates", []) if r["facet"] == "location_international"]
            ev.append("international destinations named in the corpus (articles): " + ", ".join(f"{r['label']} {r['total']}" for r in intl[:12]))
            for city, bld in builds.items():
                for name in ("World Traveller", "Travel"):
                    r = bld.records.get(name)
                    if r:
                        ev.append(f"{city} '{name}' ({r['published']}): {_pct(r['locations']['outside_home_share'])} of titles/leads name a place outside {city}")
        elif did == "D07":
            pi = [r for r in (j.records.values() if j else []) if r["kind"] == "print-issue"]
            if pi:
                yrs = Counter()
                for r in pi:
                    for y, v in r["years"].items():
                        yrs[y] += v
                ev.append(f"{len(pi)} print-issue categories, {sum(r['published'] for r in pi)} posts; by year: " + ", ".join(f"{y}: {v}" for y, v in sorted(yrs.items())))
                ev.append(f"{sum(r['single_category_articles'] for r in pi)} of those posts carry no other category -- no second prior exists")
        elif did == "D08":
            for a in affects:
                r = rec(a["city"], a["category"])
                ev.append(f"{a['category']} ({a['articles']}, {r['first_year']}-{r['last_year']}): {'; '.join(s['title'][:55] for s in r['samples'][:3])}")
        elif did == "D09":
            for city, bld in builds.items():
                ms = _members_in(bld, "Uncategorized")
                non = [a.title for a in ms if _NON_ARTICLE.search(a.title)]
                yrs = Counter(a.year for a in ms)
                ev.append(f"{city}: {len(ms)} Uncategorized ({min(yrs) if yrs else '-'}-{max(yrs) if yrs else '-'}); obvious non-articles by title: {len(non)} -> {', '.join(t[:50] for t in non[:4]) or 'none'}")
                r = bld.records.get("Uncategorized")
                if r:
                    ev.append(cue_line(city, "Uncategorized"))
        elif did == "D10":
            for city, bld in builds.items():
                multi = sum(1 for a in bld.articles if len(set(a.categories)) > 1)
                yo = sum(1 for a in bld.articles if a.primary_category_id is not None)
                primary_is_parent = sum(1 for a in bld.articles if a.primary_category_id is not None and bld.term_to_name.get(a.primary_category_id) in CONTAINERS[city])
                ev.append(f"{city}: {multi} articles ({_pct(multi / len(bld.articles))}) carry 2+ categories; Yoast primary set on {yo} ({_pct(yo / len(bld.articles))}); the primary is itself a parent container on {primary_is_parent}")
                for cname in CONTAINERS[city]:
                    r = bld.records.get(cname)
                    if r and r["published"]:
                        ev.append(f"{city} container '{cname}': {r['published']} articles, {r['single_category_articles']} carry nothing else; top co-filings: " + ", ".join(f"{c['category']} {c['articles']}" for c in r["cooccurs"]))
        elif did == "D14":
            loc_seed = [r for r in seed_terms.values() if r["facet"] == "location"]
            proposed = sorted([r for r in loc_seed if r.get("proposed")], key=lambda r: -r["total"])
            ev.append("E1.4-proposed nodes by corpus mentions (body / in titles): " + ", ".join(f"{r['slug']} {r['total']}/{sum(r['title_hits'].values())}" for r in proposed)
                      + " -- homonyms inflate solo (the word), kuningan (also the Balinese holiday), malang (alias Batu), gunawarman (alias Wijaya); trust the title counts there")
            weak = [r for r in proposed if r["total"] < 5]
            if weak:
                ev.append("proposed nodes with < 5 mentions (drop candidates): " + ", ".join(r["slug"] for r in weak))
            gaps = [r for r in vocab.get("candidates", []) if r["facet"] in ("location_bali", "location_jakarta", "location_elsewhere")]
            ev.append("places the tree lacks entirely, by mentions (body / in titles): " + ", ".join(f"{r['label']} {r['total']}/{sum(r['title_hits'].values())}" for r in gaps[:28]))
            alias = [r for r in vocab.get("alias_suggestions", []) if r["facet"] in ("location_bali", "location_jakarta", "location_elsewhere")]
            if alias:
                ev.append("alias suggestions for existing nodes (surface forms the seed lacks): " + ", ".join(f"{r['label']} <- {', '.join(r['forms'][:3])} ({r['total']})" for r in alias[:12]))
        elif did == "D15":
            cs = [r for r in seed_terms.values() if r["facet"] == "cuisine"]
            zero = [r["slug"] for r in cs if r["total"] < 10 and sum(r["title_hits"].values()) == 0]
            ev.append("seed cuisines with < 10 body mentions and 0 title mentions: " + (", ".join(zero) or "none"))
            adds = [r for r in vocab.get("candidates", []) if r["facet"] == "cuisine" and r["total"] >= 40]
            ev.append("candidate cuisines with >= 40 mentions not in the seed: " + ", ".join(f"{r['label']} {r['total']}" for r in adds[:20]))
        elif did == "D16":
            for facet in ("vibe", "occasion", "amenities", "audience", "topic"):
                zero = [r["slug"] for r in seed_terms.values() if r["facet"] == facet and r["total"] == 0]
                rare = [r["slug"] for r in seed_terms.values() if r["facet"] == facet and 0 < r["total"] < 5]
                adds = [r for r in vocab.get("candidates", []) if r["facet"] == facet and r["total"] >= 40][:8]
                ev.append(f"{facet}: unused seed terms {zero or 'none'}; rare {rare or 'none'}; frequent candidates missing: " + (", ".join(f"{r['label']} {r['total']}" for r in adds) or "none"))
        elif did == "D17":
            for city in builds:
                ev.append(cue_line(city, "Experience Offers"))
                cl = cluster_line(city, "Experience Offers")
                if cl:
                    ev.append(cl)
        elif did == "D18":
            r = rec("bali", "Explore Bali")
            if r:
                ev.append(f"Explore Bali co-filings: " + ", ".join(f"{c['category']} {c['articles']}" for c in r["cooccurs"]) + f"; {r['single_category_articles']} carry Explore Bali alone")
                ev.append(cue_line("bali", "Explore Bali"))
                cl = cluster_line("bali", "Explore Bali")
                if cl:
                    ev.append(cl)
        elif did == "D19":
            for city in builds:
                r = rec(city, "Community")
                if r:
                    ev.append(cue_line(city, "Community"))
                    ev.append(f"{city} Community: {r['first_year']}-{r['last_year']}, median first-person density {r['fp_density_median']}; coherence verdict {r['coherence']['verdict'] if r['coherence'] else 'n/a'}")
        elif did == "D20":
            for city in builds:
                ev.append(cue_line(city, "Dining Offers"))
            r = rec("bali", "Dining Offers")
            if r:
                ev.append("Bali Dining Offers by year: " + ", ".join(f"{y}: {v}" for y, v in r["years"].items()))
                cl = cluster_line("bali", "Dining Offers")
                if cl:
                    ev.append(cl)
        elif did == "D21":
            ev.append(cue_line("bali", "News"))
            r = rec("bali", "News")
            if r:
                ev.append("Bali News by year: " + ", ".join(f"{y}: {v}" for y, v in r["years"].items()))
                cl = cluster_line("bali", "News")
                if cl:
                    ev.append(cl)
        elif did == "D22":
            ev.append(f"corpus mentions -- wedding/honeymoon/proposal/bridal: {cand_total('occasion/Wedding')} articles; Bali 'Weddings' category: {rec('bali', 'Weddings')['published'] if rec('bali', 'Weddings') else 0}")
        elif did == "D23":
            r = rec("bali", "Lifestyle")
            if r:
                ev.append(f"Lifestyle ({r['published']}, {r['first_year']}-{r['last_year']}): co-filings " + ", ".join(f"{c['category']} {c['articles']}" for c in r["cooccurs"]) + f"; {r['single_category_articles']} carry Lifestyle alone")
                ev.append(cue_line("bali", "Lifestyle"))
                cl = cluster_line("bali", "Lifestyle")
                if cl:
                    ev.append(cl)
        elif did == "D25":
            for city, name in (("jakarta", "Art"), ("bali", "Art In Bali")):
                if rec(city, name):
                    ev.append(cue_line(city, name))
                    cl = cluster_line(city, name)
                    if cl:
                        ev.append(cl)
        elif did == "D26":
            ev.append(cue_line("jakarta", "Business"))
            cl = cluster_line("jakarta", "Business")
            if cl:
                ev.append(cl)
        elif did == "D27":
            for a in affects:
                r = rec(a["city"], a["category"])
                ev.append(f"{a['category']}: {a['articles']} published (WP count {r['wp_count']})")
        ev = [e for e in ev if e]
        out.append({**d, "affects": affects, "articles_affected": total, "evidence": ev, "cities": sorted({a["city"] for a in affects}) or (["jakarta", "bali"] if d["kind"] in ("vocabulary", "policy") else [])})
    return out


def assemble(builds: dict[str, CityBuild], vocab: dict, llm_meta: dict, sources_meta: dict, delta: dict | None = None) -> dict:
    decisions = decision_evidence(builds, vocab)
    missing = set(RESOLUTIONS) - {d["id"] for d in decisions}
    if missing:
        raise KeyError(f"RESOLUTIONS names decisions that are not in the registry: {sorted(missing)}")
    for d in decisions:
        res = RESOLUTIONS.get(d["id"])
        if res is None:
            raise KeyError(f"decision {d['id']} has no entry in RESOLUTIONS -- every decision must be resolved")
        d["resolution"] = {**res, "status": "resolved", "decided_by": DECIDED_BY, "decided_on": DECIDED_ON}
        d["status"] = "resolved"
    xcity = cross_city(builds)
    calib = calibration(builds)
    conflicts = [{"id": d["id"], "title": d["title"], "conflict": c} for d in decisions for c in d["resolution"]["conflicts"]]
    shared = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": f"engine/packages/taxonomy-evidence {TOOL_VERSION}",
        "llm": llm_meta,
        "sources": sources_meta,
        "resolution_meta": {
            "decided_by": DECIDED_BY, "decided_on": DECIDED_ON,
            "decisions_total": len(decisions),
            "decisions_resolved": sum(1 for d in decisions if d["status"] == "resolved"),
            "decisions_open": [d["id"] for d in decisions if d["status"] != "resolved"],
            "explicit": sorted(d["id"] for d in decisions if d["resolution"]["source"] == "explicit"),
            "as_recommended": sorted(d["id"] for d in decisions if d["resolution"]["source"] == "as-recommended"),
            "evidence_flag_policy": EVIDENCE_FLAG_POLICY["id"],
            "conflicts_with_recommendation": conflicts,
        },
        "decisions": decisions,
        "evidence_flag_policy": EVIDENCE_FLAG_POLICY,
        "rules": RULES,
        "vocabulary_delta": {"file": "engine/packages/taxonomy-evidence/vocabulary-delta.json", "human": "engine/packages/taxonomy-evidence/vocabulary-delta.md",
                             "counts": delta["counts"] if delta else None},
        "cross_city": xcity,
        "instrument_calibration": calib,
        "vocabulary": {k: v for k, v in vocab.items() if not k.startswith("_")},
    }
    models = {}
    for city, bld in builds.items():
        recs = list(bld.records.values())

        def _order(r: dict) -> tuple:
            res = r.get("resolution") or {}
            pre = r.get("e20_status") or r["status"]
            return (0 if res.get("changed") else (1 if pre in ("decision-needed", "flagged-by-evidence") else 2), -r["published"])

        recs.sort(key=_order)
        status_counts = Counter(r["status"] for r in recs)
        pre_counts = Counter(r.get("e20_status") or r["status"] for r in recs)
        still_open = [r for r in recs if r["status"] in ("decision-needed", "flagged-by-evidence")]
        coh_summary = defaultdict(list)
        for r in recs:
            c = r["coherence"]
            coh_summary[c["verdict"] if c else "n/a"].append(r["name"])
        city_decisions = [d for d in decisions if city in d["cities"] or not d["cities"]]
        models[city] = {
            **shared,
            "city": city,
            "vector_source": bld.space.source,
            "totals": {"articles": len(bld.articles), "categories": len(recs), "categories_with_articles": sum(1 for r in recs if r["published"]),
                       "flagged_categories": len(still_open),
                       "decision_needed_categories": status_counts.get("decision-needed", 0),
                       "resolved_categories": sum(1 for r in recs if (r["status"] or "").startswith("resolved")),
                       "changed_categories": sum(1 for r in recs if (r.get("resolution") or {}).get("changed")),
                       "flagged_categories_pre_resolution": pre_counts.get("decision-needed", 0) + pre_counts.get("flagged-by-evidence", 0),
                       "auto_accepted_categories": sum(1 for r in recs if r["status"] and r["status"].startswith("auto-accepted")),
                       "empty_categories": status_counts.get("empty", 0), "status_counts": dict(status_counts), "status_counts_pre_resolution": dict(pre_counts),
                       "decisions_total": len(decisions), "decisions_for_city": len(city_decisions),
                       "decisions_resolved": sum(1 for d in city_decisions if d["status"] == "resolved")},
            "categories": recs,
            "coherence_summary": dict(coh_summary),
        }
    return models
