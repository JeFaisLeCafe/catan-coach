# 01 — Define Strategy Experiment plans and schedules

**What to build:** The pure domain types and deterministic scheduler for one candidate Policy
against an Opponent Population made of one repeated Policy.

**Blocked by:** None

**Status:** resolved (shipped in `393a2f8`; corrected 2026-11-13)

## Read first

- `AGENTS.md`
- `CONTEXT.md`, especially Policy, Strategy Experiment, and Opponent Population
- `.scratch/strategy-lab/spec.md`
- `src/catan_coach/domain/corpus.py` for deterministic split/value-object style
- `src/catan_coach/domain/search.py` for frozen domain dataclasses

## Files

- Add `src/catan_coach/domain/experiment.py`
- Add `tests/test_experiment.py`
- Do not import Catanatron, engine modules, models, filesystem I/O, or CLI code

## Required interface

Define immutable, slotted value objects for:

- `PolicyPreference`: category and finite delta;
- `PolicyConfig`: submitted human name, kind (`value`, `model`, or `random`), model path and optional
  calibration-sidecar path, search simulation count, exploration flag, and declared preferences;
- `FrozenPolicySpec`: the same semantics plus required SHA-256 model hash and optional sidecar hash;
- `GameRules`: Victory Points, discard limit, friendly robber, and turn limit, with explicit
  defaults;
- `SourceProvenance`: source commit, dirty-tree flag, and optional dirty-diff hash;
- `ExperimentConfig`: submitted, unresolved Policy configs and experiment fields;
- `ExperimentPlan`: frozen Policies, rules, source provenance, and all schedule fields;
- `ScheduledGame`: result key, pairing key, seed, candidate Seat index, ordered Seat Policies, map
  policy, frozen `GameRules`, and `SourceProvenance`;
- `BehaviorCounts`: all setup/action metrics listed in the spec that exist before a game ends;
- `BehaviorProfile`: `BehaviorCounts` plus final award ownership, final public/actual Victory
  Points, and won flag;
- `PartialBehaviorProfile`: `BehaviorCounts` plus current award ownership and current public/actual
  Victory Points at the turn limit; it has no won flag;
- `CompletedGame`, `DroppedGame`, and `TechnicalFailure` as the closed status model;
- `SeatResult` and `PartialSeatResult` as defined below.

`PolicyPreference` is canonical:

- category is one of `settlement`, `city`, `road`, `development_card`, or `port`;
- delta is finite and in `[-1.0, 1.0]`;
- zero-delta entries are omitted, making an empty tuple the one zero-preference representation;
- categories appear at most once and tuples are sorted in the category order above;
- non-model Policies reject non-empty preferences.

For `PolicyConfig`/`FrozenPolicySpec`, model path/hash are required only for `kind="model"` and
forbidden for `value`/`random`. Sidecar path and hash are either both present or both absent.
`FrozenPolicySpec` rejects unresolved model hashes.

Status fields are explicit:

- Common completed/dropped fields are result/pairing keys, engine seed, map seed, candidate Seat,
  ordered frozen Seat Policies, map policy, `GameRules`, `SourceProvenance`, Catanatron package
  version, Catanatron source SHA, Plies, and turns.
- `SeatResult` requires Seat index/name, Policy name, and one final `BehaviorProfile`. The profile
  is the single source of truth for final public/actual Victory Points and won flag; do not
  duplicate those values on `SeatResult`.
- `PartialSeatResult` requires Seat index/name, Policy name, and one `PartialBehaviorProfile`.
- `CompletedGame` adds one winner Seat index and exactly four `SeatResult`s.
- `DroppedGame` adds reason `turn_limit` and exactly four `PartialSeatResult`s; it has no winner,
  won flag, or final Seat results.
- `TechnicalFailure` requires result/pairing keys, attempt number (`1` or `2`), exception type, and
  message; it has no game outcome or Behavior Profile.

Expose:

```python
schedule(plan: ExperimentPlan) -> tuple[ScheduledGame, ...]
```

Names may differ only if the resulting interface is smaller and all spec concepts remain explicit.

## Scheduling rules

- Version 1 accepts exactly four players. Reject other counts with a useful `ValueError`.
- Require at least one game per candidate Seat.
- Produce `4 * games_per_candidate_seat` entries.
- Seat the candidate exactly once in each game and exactly the requested number of times in each
  Seat; fill every other Seat with the opponent.
- Use unique deterministic seeds derived from `base_seed` and schedule position.
- Assign candidate Seats by a deterministic shuffled permutation inside each block of four
  consecutive seeds. Do not give each Seat one contiguous seed range.
- A result/pairing key must be unchanged by output directory, wall-clock time, Python hash randomization,
  or iteration over sets/dicts.
- The result key changes when any play-affecting plan field changes.
- The pairing key excludes only candidate Policy Preferences. It remains equal across Intervention
  variants and changes for every other play-affecting difference.
- Validate Policy kinds and reject a model Policy without a model path.
- `schedule()` accepts only a frozen `ExperimentPlan` and rejects a model Policy with unresolved
  model or sidecar hashes.
- Do not open model/sidecar files or inspect Git in this pure module. Freezing belongs to adapters.

## Tests

- Same plan produces byte-for-byte equivalent schedules on repeated calls.
- Candidate exposure is exactly balanced across all Seats.
- Every four-game block contains every candidate Seat exactly once.
- Seeds and result keys are unique.
- Changing base seed, search simulations, model/sidecar hash, candidate Seat in a scheduled entry,
  map policy, game rules, or source provenance changes result and pairing keys.
- Changing only candidate preferences changes result keys but not pairing keys.
- Preference tuples canonicalize category order/zero entries and reject duplicate, non-finite,
  out-of-range, or non-model preferences.
- Model/sidecar fields obey kind-specific required/forbidden and both-or-neither invariants.
- Display name is excluded from play identity; the persistence adapter must still reject opening an
  existing output directory with a differently named frozen plan.
- Invalid counts and incomplete Policy specifications fail with actionable messages.
- Completed/dropped/failure types enforce their required/forbidden fields without sentinel values.
- Tests use hand-written plans only and run without the `engine` marker.

## Non-goals

- Playing games.
- JSON or filesystem serialization.
- Confidence intervals or reports.
- General round robins, Elo, or more than one opponent Policy.
- Implementing Policy Preferences beyond storing their declared values.

## Handoff

Finish with the exact public types/functions added, test command/result, and any field whose
semantics still need a decision. Do not broaden this ticket to engine execution.
