"""Orchestrates one city's extraction + dedup run. See README.md for the
full design rationale and the two load-bearing findings this ticket
surfaced (city-mismatched `places`/`events`, and the classification-
reviews mismatch).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from now_place_extraction.db import (
    ArticleRecord,
    PlaceRow,
    fetch_articles,
    fetch_places,
    find_or_create_place,
    make_engine,
    slugify,
    upsert_mention,
)
from now_place_extraction.dedup import cluster_candidates
from now_place_extraction.extract import extract_candidates, is_non_venue_phrase, looks_venue_shaped, plausible_new_place
from now_place_extraction.gazetteer import Gazetteer, KnownPlace
from now_place_extraction.reviewqueue import write_review_queue
from now_place_extraction.textwalk import flatten


# A mention within this many characters of the article start is tagged
# `role='featured'` rather than `mentioned` -- a heuristic proxy for "this
# article is substantially ABOUT this venue" (e.g. named in the opening
# paragraph) vs. a passing reference deeper in the piece. Documented
# assumption, not a discovered constant.
FEATURED_OFFSET_THRESHOLD = 200

EXISTING_FUZZY_FLOOR = 0.80

# The ORIGINAL 177 loader-seeded `now_jakarta.public.places` rows this
# ticket's report documents as Bali-origin content (Finding #1): ids 4-180,
# plus 14237-14239 which were briefly (and mistakenly) deleted mid-ticket
# and re-inserted under new ids -- see the report's "corrections made
# during this run" section. Used ONLY to scope the Finding #1 warning on a
# fuzzy-match review row to the rows it's actually about; a fuzzy match
# against a place this SAME pipeline created earlier in the run (e.g. on
# a second, idempotency-check run) is unrelated to that data-placement bug
# and gets the generic note instead.
JAKARTA_ORIGINAL_CONTAMINATED_IDS = frozenset(range(4, 181)) | {14237, 14238, 14239}


@dataclass
class CityReport:
    city: str
    articles_processed: int = 0
    raw_candidates: int = 0
    candidates_after_noise_filter: int = 0
    exact_matches_to_existing: int = 0
    fuzzy_matches_to_existing_queued: int = 0
    new_places_created: int = 0
    new_place_clusters_merged_members: int = 0
    mentions_inserted: int = 0
    mentions_already_present: int = 0
    review_pairs_new_vs_new: int = 0
    review_pairs_omitted_low_evidence: int = 0
    review_pairs_omitted_over_cap: int = 0
    review_rows_written: int = 0
    recurring_unconfirmed_new_places: int = 0
    llm_calls_used: int = 0
    sample_created_places: list[str] = field(default_factory=list)


def run_city(
    *,
    city: str,
    db_ref: str,
    content_dir: Path,
    limit: int | None = None,
    dry_run: bool = False,
    llm_adjudicate=None,
) -> CityReport:
    engine = make_engine(db_ref)
    report = CityReport(city=city)

    known_places = [KnownPlace(id=p.id, name=p.name, slug=p.slug, org_id=p.org_id, status=p.status) for p in fetch_places(engine)]
    gazetteer = Gazetteer(known_places)

    articles = fetch_articles(engine, limit=limit)
    report.articles_processed = len(articles)

    # article_id -> list[(candidate_surface, start, end)] resolved to an
    # EXISTING place (exact tier) -- committed as mentions directly.
    exact_hits: list[tuple[ArticleRecord, str, int, int, int]] = []  # (article, surface, start, place_id)

    # fuzzy hits against an existing place -- never auto-linked, always reviewed.
    fuzzy_review_rows: list[dict] = []

    # surface_text -> list[(article, start)] for candidates with NO gazetteer hit at all.
    new_candidate_occurrences: dict[str, list[tuple[ArticleRecord, int]]] = defaultdict(list)
    new_candidate_article_ids: dict[str, set[int]] = defaultdict(set)

    for article in articles:
        text = flatten(article.body_blocks)
        if not text:
            continue
        candidates = extract_candidates(text)
        report.raw_candidates += len(candidates)
        for cand in candidates:
            match = gazetteer.lookup(cand.surface_text, fuzzy_floor=EXISTING_FUZZY_FLOOR)
            if match is not None and is_non_venue_phrase(match.place.name):
                # The gazetteer itself can hold a bare geographic-area name
                # (found live: `now_jakarta.public.places` id=4 is literally
                # named "Bali" -- one of the 177 rows Finding #1 documents
                # as misplaced Bali content). An EXACT string match against
                # such a row is real but useless: every article that merely
                # mentions the region "Bali" in passing would otherwise
                # become a `place_mention`, which is exactly the kind of
                # noise this pipeline works to keep out of new candidates
                # (see plausible_new_place / is_non_venue_phrase) -- the
                # same standard has to apply to a gazetteer hit, not just a
                # brand-new one. Treated as no match at all (not even
                # queued for review -- there's nothing for a human to
                # decide here).
                continue
            if match is not None and match.tier == "exact":
                exact_hits.append((article, cand.surface_text, cand.start, cand.end, match.place.id))
            elif match is not None and match.tier == "fuzzy":
                fuzzy_review_rows.append(
                    {
                        "kind": "candidate_matches_existing_place",
                        "city": city,
                        "article_id": article.id,
                        "surface_text": cand.surface_text,
                        "offset": cand.start,
                        "existing_place_id": match.place.id,
                        "existing_place_name": match.place.name,
                        "score": round(match.score, 4),
                        "note": (
                            "Jakarta's 177 pre-existing places are known to be Bali-origin content "
                            "(see this ticket's report, Finding #1) -- verify this is a genuine "
                            "mention of that real venue before merging, not an artifact of that "
                            "data placement bug."
                            if city == "jakarta" and match.place.id in JAKARTA_ORIGINAL_CONTAMINATED_IDS
                            else "Below the exact-match tier -- verify before linking."
                        ),
                    }
                )
            else:
                new_candidate_occurrences[cand.surface_text].append((article, cand.start))
                new_candidate_article_ids[cand.surface_text].add(article.id)

    # ---- noise filter for brand-new (no gazetteer hit) candidates ----
    #
    # v2, tightened after a hand-inspected sample of the v1 output (both by
    # this pipeline's own author and independently by the coordinator, on
    # Jakarta and Bali respectively) measured real precision far below an
    # acceptable bar: menu items ("Herb Roasted Lamb Chop", "Martini Rosso
    # 5ml"), copy fragments ("CONTINUES EVERY WEDNESDAY", "A Night"),
    # countries ("South Wales", "Germany and Canada"), person names ("Made
    # Bandem", "John Eales", "Ardhito Pramono") and generic concepts
    # ("Hindu Bali") were all created as real `places` rows. A recurrence-
    # based fallback (v1: "recurs in >=2 distinct articles OR looks venue-
    # shaped") is exactly what let those through -- a person quoted across
    # two different event write-ups, or a stock phrase reused by the same
    # writer, recurs just as reliably as a real venue does.
    #
    # v2 requires an explicit venue keyword UNCONDITIONALLY for a brand-new
    # candidate to become a `places` row -- there is no recurrence-only
    # path anymore, for single- or multi-token candidates alike. This is a
    # deliberate, large recall cut (a real venue whose own name carries no
    # type word at all, e.g. "Marina Bay Sands", is no longer auto-created)
    # in exchange for precision, exactly the bias the ticket states
    # ("prefer precision; route uncertain merges to review rather than
    # guessing") and the coordinator's follow-up direction ("route low-
    # confidence extractions to review rather than creating places rows").
    # Non-keyword candidates that still recur often are not discarded --
    # they carry real signal a human can act on -- so they are written to
    # the file-based review queue (`recurring_unconfirmed_new_place`,
    # pipeline.py below) instead of the database.
    MIN_RECURRENCE_FOR_REVIEW_ONLY = 3

    surviving_counts: dict[str, int] = {}
    recurring_unconfirmed: list[tuple[str, int]] = []  # (surface, distinct_article_count) -- review-only, never a DB row
    for surface, occurrences in new_candidate_occurrences.items():
        if not plausible_new_place(surface):
            continue  # pure noise word(s) -- see extract.plausible_new_place
        recurrence = len(new_candidate_article_ids[surface])
        if looks_venue_shaped(surface):
            surviving_counts[surface] = len(occurrences)
        elif recurrence >= MIN_RECURRENCE_FOR_REVIEW_ONLY:
            recurring_unconfirmed.append((surface, recurrence))
    report.candidates_after_noise_filter = sum(surviving_counts.values())

    dedup_result = cluster_candidates(surviving_counts, llm_adjudicate=llm_adjudicate)
    report.review_pairs_new_vs_new = len(dedup_result.review_pairs)
    if llm_adjudicate is not None:
        report.llm_calls_used = getattr(llm_adjudicate, "calls_made", 0)

    # ---- commit exact hits to existing places ----
    for article, surface, start, _end, place_id in exact_hits:
        role = "featured" if start < FEATURED_OFFSET_THRESHOLD else "mentioned"
        if dry_run:
            report.mentions_inserted += 1
            continue
        inserted = upsert_mention(engine, article_id=article.id, place_id=place_id, offset=start, surface_text=surface, role=role)
        if inserted:
            report.mentions_inserted += 1
        else:
            report.mentions_already_present += 1
    report.exact_matches_to_existing = len(exact_hits)
    report.fuzzy_matches_to_existing_queued = len(fuzzy_review_rows)

    # ---- commit new-place clusters ----
    member_to_canonical: dict[str, str] = {}
    for cluster in dedup_result.clusters:
        for m in cluster.members:
            member_to_canonical[m] = cluster.canonical_name

    canonical_to_place_id: dict[str, int] = {}
    for cluster in dedup_result.clusters:
        if dry_run:
            report.new_places_created += 1
            report.new_place_clusters_merged_members += len(cluster.members) - 1
            if len(report.sample_created_places) < 15:
                report.sample_created_places.append(cluster.canonical_name)
            continue
        place_id, created = find_or_create_place(engine, name=cluster.canonical_name, preferred_slug=slugify(cluster.canonical_name))
        canonical_to_place_id[cluster.canonical_name] = place_id
        if created:
            report.new_places_created += 1
            report.new_place_clusters_merged_members += len(cluster.members) - 1
            if len(report.sample_created_places) < 15:
                report.sample_created_places.append(cluster.canonical_name)

    if not dry_run:
        for surface, occurrences in new_candidate_occurrences.items():
            if surface not in member_to_canonical:
                continue
            place_id = canonical_to_place_id.get(member_to_canonical[surface])
            if place_id is None:
                continue
            for article, start in occurrences:
                role = "featured" if start < FEATURED_OFFSET_THRESHOLD else "mentioned"
                inserted = upsert_mention(engine, article_id=article.id, place_id=place_id, offset=start, surface_text=surface, role=role)
                if inserted:
                    report.mentions_inserted += 1
                else:
                    report.mentions_already_present += 1

    # ---- write review queue ----
    # A raw dump of every sub-0.85 pair is not a REVIEWABLE queue -- most
    # are noise-candidate-vs-noise-candidate pairs nobody will ever look
    # at (measured live: tens of thousands of them, see report). Two cuts
    # make it human-sized without hiding anything real: (1) both sides
    # must recur at least twice -- a pair where either side was seen only
    # once is exactly the kind of ungrounded single mention already
    # excluded everywhere else in this pipeline; (2) a hard cap, ranked
    # by how much evidence exists for the pair (combined mention count) --
    # the omitted count is reported, not silently dropped from the count.
    MIN_MENTIONS_EACH_SIDE = 2
    MAX_REVIEW_ROWS = 2000

    recurring_unconfirmed.sort(key=lambda t: -t[1])
    report.recurring_unconfirmed_new_places = len(recurring_unconfirmed)
    unconfirmed_rows = [
        {
            "kind": "recurring_unconfirmed_new_place",
            "city": city,
            "surface_text": surface,
            "distinct_articles": recurrence,
            "note": (
                f"Recurs in {recurrence} distinct articles but carries no venue keyword "
                "(extract.VENUE_KEYWORDS) -- NOT created as a places row (v2 precision gate). "
                "Could be a real venue whose name has no type word (e.g. 'Marina Bay Sands'), "
                "or a person/org/generic phrase that simply repeats. Verify by hand before creating."
            ),
        }
        for surface, recurrence in recurring_unconfirmed[:MAX_REVIEW_ROWS]
    ]

    candidate_pair_rows = []
    for pair in dedup_result.review_pairs:
        mentions_a = surviving_counts.get(pair.name_a, 0)
        mentions_b = surviving_counts.get(pair.name_b, 0)
        if mentions_a < MIN_MENTIONS_EACH_SIDE or mentions_b < MIN_MENTIONS_EACH_SIDE:
            continue
        candidate_pair_rows.append(
            {
                "kind": "possible_duplicate_new_places",
                "city": city,
                "name_a": pair.name_a,
                "name_b": pair.name_b,
                "score": round(pair.result.score, 4),
                "full_ratio": round(pair.result.full_ratio, 4),
                "core_jaccard": round(pair.result.core_jaccard, 4),
                "mentions_a": mentions_a,
                "mentions_b": mentions_b,
                "note": "Below the 0.85 auto-merge gate -- both were created as separate places; verify by hand.",
            }
        )
    candidate_pair_rows.sort(key=lambda r: -(r["mentions_a"] + r["mentions_b"]))
    kept_pairs = candidate_pair_rows[:MAX_REVIEW_ROWS]
    report.review_pairs_omitted_low_evidence = len(dedup_result.review_pairs) - len(candidate_pair_rows)
    report.review_pairs_omitted_over_cap = max(0, len(candidate_pair_rows) - MAX_REVIEW_ROWS)

    review_rows = list(fuzzy_review_rows) + kept_pairs + unconfirmed_rows
    report.review_rows_written = len(review_rows)
    if not dry_run:
        write_review_queue(content_dir / "place_merge_review_queue.jsonl", review_rows)

    return report
