"""QA.6 — independent adversarial check that all three exclusion paths agree
on a NULL candidate type, and that known venue types still behave (F68's
guarantee must not have regressed).

Run: engine/packages/filters/.venv/Scripts/python.exe qa6_f73_three_paths.py
(needs now_filters, now_rails on path -- run from within filters venv with
PYTHONPATH extended, or invoke via the harness below).
"""
import sys, os

sys.path.insert(0, os.path.join("..", "filters", "src"))

from now_filters.type_relations import TypeRelation, is_competitor, excluded_types_for
from now_filters.ladder import _enforce_competitor_invariant
from now_filters.models import Candidate

RELATIONS = {
    "stay": TypeRelation(type="stay", exclude_same=True, complements=("eat", "drink", "wellness", "do")),
    "eat": TypeRelation(type="eat", exclude_same=True, complements=("drink", "do", "event")),
    "editorial": TypeRelation(type="editorial", exclude_same=False, complements=("stay","eat","drink","wellness","do","shop","event","editorial")),
}

def sql_would_pass(candidate_type, excluded):
    """Mirrors hard.py's `primary_type IS NOT NULL AND primary_type::text != ALL(:excluded)`."""
    if candidate_type is None:
        return False  # IS NOT NULL guard fails closed
    return candidate_type not in excluded

fails = []

# --- Case A: known subject (stay), NULL candidate type -> must be excluded everywhere ---
subject_type = "stay"
excluded = excluded_types_for(RELATIONS, subject_type)
sql_pass = sql_would_pass(None, excluded)
py_pass = not is_competitor(RELATIONS, subject_type, None)  # True passes (not excluded)
cand = Candidate(entity_type="place", entity_id=1, type=None, subtype=None, status="active",
                  area_term=None, org_id=None, price_band=None, format=None, series_key=None,
                  quality_score=None, lat=None, lng=None, distance_m=None, amenities=frozenset(),
                  hours=(), ends_at=None, is_paid=False, published_at=None)
ladder_pass = len(_enforce_competitor_invariant([cand], RELATIONS, subject_type)) == 1

print(f"[known subject, NULL candidate] sql_would_pass={sql_pass} is_competitor_says_pass={py_pass} ladder_survives={ladder_pass}")
if sql_pass or py_pass or ladder_pass:
    fails.append("NULL candidate leaked through at least one path when subject is known+exclude_same")

# --- Case B: unknown subject (None), known non-competitor candidate type ---
excluded2 = excluded_types_for(RELATIONS, None)
sql_pass2 = sql_would_pass("eat", excluded2)
py_pass2 = not is_competitor(RELATIONS, None, "eat")
cand2 = Candidate(entity_type="place", entity_id=2, type="eat", subtype=None, status="active",
                   area_term=None, org_id=None, price_band=None, format=None, series_key=None,
                   quality_score=None, lat=None, lng=None, distance_m=None, amenities=frozenset(),
                   hours=(), ends_at=None, is_paid=False, published_at=None)
ladder_pass2 = len(_enforce_competitor_invariant([cand2], RELATIONS, None)) == 1
print(f"[unknown subject, known candidate] sql_would_pass={sql_pass2} is_competitor_says_pass={py_pass2} ladder_survives={ladder_pass2}")
if sql_pass2 or py_pass2 or ladder_pass2:
    fails.append("Known candidate passed even though subject is unknown -- F68 says exclude everything venue-shaped")

# --- Case C (regression guard): known non-venue subject (editorial), NULL candidate ---
# exclude_same=False for editorial -> excluded_types_for returns empty -> nothing to guard against
excluded3 = excluded_types_for(RELATIONS, "editorial")
sql_pass3 = sql_would_pass(None, excluded3) if excluded3 else True  # SQL clause not applied when excluded is empty in practice; is_competitor models it directly
py_pass3 = not is_competitor(RELATIONS, "editorial", None)
print(f"[editorial subject (exclude_same=False), NULL candidate] excluded_set={excluded3} is_competitor_says_pass={py_pass3}")
if not py_pass3:
    fails.append("editorial subject wrongly excludes a NULL candidate -- over-correction regression")

# --- Case D (F68 regression guard): known subject/known competing candidate must STILL be excluded ---
py_pass4 = not is_competitor(RELATIONS, "stay", "stay")
cand4 = Candidate(entity_type="place", entity_id=4, type="stay", subtype=None, status="active",
                   area_term=None, org_id=None, price_band=None, format=None, series_key=None,
                   quality_score=None, lat=None, lng=None, distance_m=None, amenities=frozenset(),
                   hours=(), ends_at=None, is_paid=False, published_at=None)
ladder_pass4 = len(_enforce_competitor_invariant([cand4], RELATIONS, "stay")) == 1
print(f"[known stay subject, known stay candidate] is_competitor_says_pass={py_pass4} ladder_survives={ladder_pass4}")
if py_pass4 or ladder_pass4:
    fails.append("F68 regressed: a known same-type competitor is no longer excluded")

print()
if fails:
    print("RESULT: FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
else:
    print("RESULT: PASS -- all three paths agree, and known-type exclusion (F68) is intact.")
