# 04 — Run one scheduled game

**What to build:** The Catanatron adapter that constructs declared Policies, plays one
`ScheduledGame`, tracks behavior, and returns one deterministic `GameResult`.

**Blocked by:** 01, 02, 03

**Status:** ready-for-agent

## Read first

- `.scratch/strategy-lab/spec.md`
- Implemented interfaces from issues 01 and 03
- `src/catan_coach/engine/corpus.py` for player construction, turn limits, model caching, and map use
- `src/catan_coach/engine/model_player.py`
- `src/catan_coach/engine/board.py`
- `src/catan_coach/models/gbdt.py`

## Files

- Add `src/catan_coach/engine/experiment.py`
- Add `tests/test_engine_experiment.py`
- Reuse existing modules; do not copy the Corpus game loop or model loader wholesale

## Required interface

```python
play_scheduled_game(game: ScheduledGame) -> CompletedGame | DroppedGame
```

Dependencies such as model loading may be accepted explicitly if that makes tests faster, but the
external interface must hide Catanatron types from callers.

## Policy construction

- `value` creates one Catanatron `ValueFunctionPlayer`.
- `model` loads the exact hashed model plus calibration sidecar and creates
  `WinProbabilityPlayer` with the declared search simulations and exploration flag.
- `random` is allowed only for tests/smoke plans and must be visibly named in results.
- Cache loaded models per worker by resolved path plus model/sidecar hash.
- Fail before play if current file hashes do not match the frozen Policy specification.
- Never silently substitute `vp-share` or another baseline for a missing model.

## Game construction

- Preserve the exact Seat order from `ScheduledGame`.
- Catanatron shuffles the supplied player list with the game RNG. Invert that deterministic
  permutation when constructing the input list so the candidate occupies the scheduled Seat in
  `game.state.players`; assert the actual Seat before the first Action.
- Seed the Game with the scheduled seed.
- Use `corpus_map(seed)` unless the plan declares another supported map policy.
- Apply declared victory target, discard limit, and friendly-robber settings.
- Use the frozen `GameRules` turn limit. A game hitting it returns `DroppedGame`, not
  `TechnicalFailure`.
- Keep random streams deterministic. Search copies must not consume the live game's dice stream.
- Record and verify the pinned Catanatron version. Freeze every RNG source used by seating, map,
  development deck, Action exploration, search copies, and live game play.

## Execution

- Observe every executed action through the Behavior Tracker.
- Record Plies and completed turns.
- Return one `SeatResult` for every Seat and one Behavior Profile per Seat.
- Include engine version/pin, model/sidecar hashes, seed, map seed, result key, and pairing key.
- Do not catch arbitrary exceptions. The orchestration adapter records a `TechnicalFailure`
  attempt with exception type/message and retries once. Programmer assertions remain visible in
  tests and must not become dropped games.

## Tests

- A tiny random/value plan returns four Seat results and exactly one winner when it terminates.
- Candidate Seat and Policy names match the schedule.
- Candidate actual Seat remains correct across several seeds despite Catanatron's input shuffle.
- Same scheduled game produces the same result document twice, excluding explicitly documented
  non-deterministic metadata (preferably none).
- Different seeds produce independently identified results.
- A deliberately tiny turn limit produces the declared dropped status.
- A missing/changed model or sidecar fails before the first Ply.
- Model search does not mutate the live RNG beyond actual game Actions.
- Worker/process order cannot change any result field.
- Mark all tests `engine` and keep them small enough for the full suite.

## Performance

- Do not add multiprocessing in this ticket.
- One runner call owns one game and has no global output side effects.
- Avoid storing Position snapshots or Observation matrices in the result.

## Non-goals

- Scheduling, persistence, CLI, reports, confidence intervals, or interventions.
- Training a model.
- Browser presentation.

## Handoff

Give the orchestration agent the exact call, expected failure type, measured smoke-game runtime, and
any Catanatron global state that had to be controlled.
