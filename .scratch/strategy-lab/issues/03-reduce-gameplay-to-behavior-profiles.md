# 03 — Reduce gameplay to Behavior Profiles

**What to build:** One engine-side reducer that observes a live Catanatron game and produces the
per-Seat Behavior Profiles declared in the Strategy Lab spec.

**Blocked by:** 01

**Status:** resolved (shipped in `393a2f8`; corrected 2026-11-13)

## Read first

- `.scratch/strategy-lab/spec.md`, especially Game Result and Behavior Profile
- `CONTEXT.md` definition of Behavior Profile
- `src/catan_coach/engine/review.py` for replaying `ActionRecord`s
- `src/catan_coach/engine/lines.py` and `features.py` for board/Action interpretation
- The reference concepts in `docs/references/README.md`; do not import `catan-game`

## Files

- Add `src/catan_coach/engine/behavior.py`
- Add `tests/test_behavior.py`
- Do not edit issue 01's frozen domain result schema. If a required metric is missing, stop and
  report the blocker for an integration-level schema decision.

## Interface

The runner must be able to:

```python
tracker = BehaviorTracker.start(game)
tracker.observe(before_game, action, record, after_game)
profiles = tracker.finish(game)
```

Equivalent names are acceptable. Keep Catanatron state traversal inside this module so experiment
execution and later coaching code do not duplicate metric definitions.

## Required metrics per Seat

- initial distinct resource count across the two setup settlements;
- initial production pips: for each adjacent numbered tile of each setup settlement, add
  `round(number_probability(number) * 36)`; a tile adjacent to both settlements contributes twice,
  matching two producing buildings;
- whether either setup settlement is adjacent to a port;
- post-setup settlements, cities, and roads built;
- development cards bought;
- knights played;
- domestic offers made, offers accepted, and trades completed;
- maritime trades completed;
- first post-setup purchase/build category;
- final Longest Road ownership;
- final Largest Army ownership;
- final public/actual Victory Points and won flag.

## Semantic rules

- Setup settlements and roads do not count as post-setup builds.
- Initial resource diversity counts resource kinds, not tiles; desert contributes nothing.
- Initial pips are traditional integer dice pips (2/12 = 1 through 6/8 = 5), not a floating-point
  probability. A shared adjacent tile contributes once per settlement.
- A domestic offer, acceptance, and confirmed exchange are three different facts.
- Buying a development card and playing one are different facts.
- Award ownership is the final owner in version 1; do not infer how long it was held.
- Hidden information may be used inside simulation results, but profile fields remain aggregate and
  contain no opponent hand snapshots.
- Do not infer intent, goals, “good trades,” affordability, or causality.

## Testing

- Use a deterministic scripted engine game or directly execute a short legal sequence.
- Assert setup builds are excluded while their resources/pips/port facts are included.
- Assert settlement/city/road/dev-card/knight counters independently.
- Assert maritime trade and domestic offer/accept/confirm are not conflated.
- Assert final award and win fields.
- Assert observing the same sequence twice produces equal profiles.
- Mark Catanatron-touching tests with `engine`; pure helper tests may remain fast.

## Edge cases

- A setup settlement touching the same resource on two tiles.
- No port and a generic 3:1 port.
- An offered trade rejected by every Seat.
- Multiple acceptees before the proposer confirms one.
- No winner because the turn limit was reached.
- A development Victory Point that changes actual but not public points.

## Non-goals

- Persisting every event.
- Resource-production totals or blocked-production estimates.
- Rendering prose advice.
- Computing win rates.
- Modifying Catanatron or the older TypeScript engine.

## Handoff

List every metric and its exact denominator/counting rule. If any required metric cannot be
obtained reliably from the pinned engine, stop and report the engine fact rather than inventing an
approximation.
