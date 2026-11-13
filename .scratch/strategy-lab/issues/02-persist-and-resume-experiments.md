# 02 — Persist and resume Strategy Experiments

**What to build:** A filesystem adapter that freezes one Experiment Plan, writes one atomic result
per scheduled game, and resumes without replaying completed games.

**Blocked by:** 01

**Status:** resolved (shipped in `393a2f8`; corrected 2026-11-13)

## Read first

- `.scratch/strategy-lab/spec.md`
- Issue 01 and its implemented domain interface
- `src/catan_coach/engine/corpus.py`, especially per-game writes and resume behavior
- `src/catan_coach/engine/mixture.py` for reading many game artifacts without hidden global state

## Files

- Add `src/catan_coach/engine/experiment_store.py`
- Add `tests/test_experiment_store.py`
- This adapter may perform filesystem I/O but must not import Catanatron or play games

## Directory contract

An experiment directory contains:

```text
plan.json
games/
  <result-key>.json
failures/
  <result-key>/
    attempt-1.json
    attempt-2.json
```

`plan.json` is written before any game starts. A result is written to a temporary sibling and
atomically renamed only after valid JSON is complete.

## Required behavior

- Freeze an `ExperimentConfig` plus caller-supplied `SourceProvenance` into an `ExperimentPlan`.
- Resolve every model Policy's path to a SHA-256 content hash before freezing `plan.json`.
- Resolve and hash the explicitly configured calibration sidecar. A changed sidecar changes the
  frozen Policy. Do not discover an undeclared sidecar after the plan is frozen.
- Store paths for traceability, but use hashes for identity.
- Refuse to resume if the requested frozen plan differs from `plan.json`; print or return the
  first useful mismatch rather than only “plans differ.”
- Return pending `ScheduledGame` entries in deterministic schedule order.
- Treat only a valid `CompletedGame` or `DroppedGame` with the matching result key as complete.
- Keep `TechnicalFailure` attempts separate. Retry once after the first failure. After two total
  attempts, the game is terminally failed and is not returned as pending unless the caller
  explicitly requests a reset.
- Validate loaded result documents and reject truncated, malformed, duplicate, or mismatched files.
- Never infer completion from the number of files.

## Suggested interface

```python
frozen_plan = freeze_config(config, source_provenance)
store = ExperimentStore.open(path, frozen_plan)
pending = store.pending(schedule)
store.write_result(result)
store.write_failure(failure)
outcomes = store.read_outcomes()
failures = store.read_failures()
```

`TechnicalFailure.attempt` is the single source of truth for its attempt number. The store derives
the file name from it and rejects a duplicate or out-of-order attempt.

Use one deep interface; callers should not know temporary-file names or JSON details.

## Serialization

- Use explicit version fields for the plan and result schemas.
- Use a separate versioned schema for `TechnicalFailure` attempts.
- Serialize enums/literals as stable strings and tuples as JSON arrays.
- Sort JSON object keys and terminate files with a newline for reviewable artifacts.
- Do not serialize wall-clock timestamps into deterministic game results. Optional run metadata may
  live in a separate non-comparison file.

## Tests

- Opening an empty directory writes `plan.json`.
- Reopening the same plan succeeds; a play-affecting change fails.
- One completed result disappears from `pending`; unrelated or malformed files do not.
- One dropped result also disappears from `pending` and remains distinguishable when loaded.
- First failure remains pending; second failure becomes terminal.
- Simulate interruption before rename and verify the game remains pending.
- Model or sidecar byte changes produce a plan mismatch.
- Result round-trip preserves all domain fields.
- Duplicate/mismatched result or pairing keys fail loudly.
- Tests use `tmp_path`, contain no Catanatron imports, and run in the fast suite.

## Non-goals

- Parallel workers.
- Report formatting.
- Playing or retrying games.
- Database storage.
- Corpus compatibility.

## Handoff

Report the JSON schema versions, public adapter interface, and the exact mismatch/error behavior so
the orchestration agent can call it without reading the implementation.
