# now-itinerary

E5 — the itinerary engine. ARCHITECTURE.md §12.

> **§1 principle 4: "Deterministic engine decides, LLM narrates."**
> This package is the deciding half. E5.5's narration writes prose about
> what was picked and picks nothing.

## Why a constraint solver

Not because CP-SAT finds a *better* itinerary than a language model would.
Because "no closed venues, travel budget respected, category diversity,
price ceiling" becomes **programmatically checkable** — which is what lets
§12 gate at 100% instead of hoping.

That gate is [`validate.py`](src/now_itinerary/validate.py), and it is
deliberately an *independent re-derivation* of every rule rather than a
read-back of the solver's own variables. Checking that CP-SAT satisfied
the constraints CP-SAT was given proves only that CP-SAT works. It cannot
catch the failure that actually matters: the model encoding the **wrong**
constraint. When solver and validator disagree, there is a real bug either
way.

## What the model decides

Which stop fills each `(day, slot)`, and when the visitor arrives.

It does **not** decide the order within a day — the slot ladder already
fixes that (breakfast precedes lunch precedes dinner), so there is no
travelling-salesman freedom left. What remains is scheduling: arrival
times that respect opening hours, dwell, and travel from the previous
stop.

```
breakfast → morning → lunch → afternoon → dinner → night
   eat       do/…     eat*     do/…        eat*    drink/eat
                      required             required
```

`stay` is eligible for no slot. A hotel is where the visitor sleeps, not a
stop on the route; accommodation belongs to the trip, not the timeline.

## Design notes worth knowing

**Eligibility is structural.** A stop that cannot legally fill a slot —
wrong type, closed at that hour, violates a party constraint, over the
per-stop price ceiling — has no variable created for that `(day, slot)`.
Constraints that cannot be violated because the variable does not exist
are cheaper to solve and impossible to weaken later by accident. Same
reasoning §8.G applies to pushing selective filters into SQL.

**Unknown is not yes.** `wheelchair_accessible=None` means nobody recorded
it. An accessibility requirement excludes unknowns; so do `halal` and
`vegetarian`. Promising step-free access on missing data is the error that
ends a day out.

**Missing hours are the one deliberate asymmetry.** A stop with *no* hours
data at all is treated as schedulable, because only 24 of Jakarta's places
carry hours today and failing closed on the rest would empty every
itinerary. Those stops are reported as `unverified_hours` rather than
silently blessed — the gate can be run in either mode.

**Travel times are estimates until E5.1.** `HaversineMatrix` is
straight-line distance over a fixed average speed. §15's own framing is
that "Jakarta traffic is the problem", so this is wrong in a predictable
direction: **optimistic**. `TravelMatrix.is_estimate` is on the Protocol
so a gate can refuse to certify a trip whose travel budget was only ever
checked against a guess. `PrecomputedMatrix` is the shape E5.1 fills from
`engine.travel_matrix`.

**`max_per_type_per_day` defaults to 3, not 2.** The ladder has three
`eat` slots. A cap of 2 does not read as "less repetitive", it reads as
"no breakfast, ever" — measured: 10 of 12 slots filled across two days,
breakfast dropped both, silently, because it is the only optional one of
the three.

## Infeasibility is diagnosed, not shrugged at

A bare `INFEASIBLE` tells a caller nothing actionable. `solver._precheck`
catches the conflicts that are arithmetic rather than combinatorial and
names them:

```
$ now-itinerary demo --days 4 --stops 12
infeasible: 8 distinct 'eat' stops are needed to fill the required slots
across 4 day(s), but only 5 are usable (5 eligible, reduced by
max_per_org=1). Widen the candidate pool, shorten the trip, or raise
max_per_org.
```

## Scale

`MAX_CANDIDATES_PER_SLOT = 40` bounds the model — travel feasibility needs
a constraint per `(stop, stop)` pair across consecutive slots, which is
quadratic. Taking the best-scoring N per slot is the same "re-rank the top
~40" move §7 makes for rails.

| candidates | days | solve | status |
|---|---|---|---|
| 50 | 2 | 74 ms | OPTIMAL |
| 150 | 3 | 286 ms | OPTIMAL |
| 400 | 5 | 925 ms | OPTIMAL |
| 1000 | 7 | 1.2 s | OPTIMAL |

## Repeated solves may differ — on purpose

Two solves of the same request can return different itineraries. Both are
optimal; they tie on objective. Forcing identical output was tried twice
and cost more than the problem each time:

| attempt | result |
|---|---|
| rank tie-break in the objective | needs ~1e6 headroom, pushing coefficients to ~1e9 — walked off CP-SAT's large-coefficient cliff; a 400-stop solve went 1 s → 10 s time-limit **without** proving optimality |
| `num_search_workers = 1` + fixed seed | 150 stops / 3 days measured **10.2 s FEASIBLE** vs **413 ms OPTIMAL** on 8 workers — 25× slower and no longer optimal |

And a solve that hits its time limit is nondeterministic for timing
reasons regardless, so option ② buys determinism only while it happens to
finish early.

What makes a shared itinerary stable is **persistence, not
reproducibility**: E5.4 writes the solved trip to `engine.itineraries` and
shares it by token, so a link shows the stored day out — never a re-solve.
The test therefore pins the property that matters: every solve is valid,
and they are all *equally good*.

## Try it

```bash
now-itinerary demo --days 2 --children 2 --budget 30
now-itinerary demo --wheelchair          # watch the pool collapse
now-itinerary demo --partner-stops 2     # guaranteed placements
```

## Not built yet

| | |
|---|---|
| E5.1 | OSRM travel matrix + traffic sampling → `engine.travel_matrix` |
| E5.4 | `public.places` → `Stop` adapter, itinerary API + persistence |
| E5.5 | LLM narration (**narrates only; never selects or reorders**) |
| E5.6 | Curated itineraries as content |
| E5.7 | Share / fork / edit |
