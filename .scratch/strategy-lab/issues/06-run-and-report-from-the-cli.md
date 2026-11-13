# 06 — Run and report Strategy Experiments from the CLI

**What to build:** Thin CLI orchestration for validated plan files, resumable execution, optional
parallel workers, and report generation.

**Blocked by:** 02, 04, 05

**Status:** resolved (shipped in `393a2f8`; corrected 2026-11-13)

## Read first

- `.scratch/strategy-lab/spec.md`
- Completed interfaces and handoffs from issues 01–05
- `src/catan_coach/cli.py`
- `src/catan_coach/engine/corpus.py` for bounded `ProcessPoolExecutor` use and progress reporting

## Files

- Update `src/catan_coach/cli.py`
- Add a small plan JSON adapter if needed; keep it outside the pure domain
- Add/extend `tests/test_cli.py`
- Add one engine-marked end-to-end test in `tests/test_engine_experiment.py` or a focused file

## Commands

Implement:

```text
catan-coach lab run PLAN.json --out EXPERIMENT_DIR [--workers N]
catan-coach lab report EXPERIMENT_DIR [--json OUT.json] [--markdown OUT.md]
```

Reserve `lab compare` for issue 07; do not expose a placeholder that silently does nothing.

## Plan JSON contract

- Reject unknown fields so typos cannot change an experiment silently.
- Validate all domain invariants before creating output files.
- Resolve relative model/sidecar paths relative to the plan file, not the process working
  directory. Output comes only from required `--out` and is not part of play identity.
- Freeze model and sidecar hashes into `plan.json` before games start.
- Refuse a dirty source tree by default. An explicit `--allow-dirty` records the commit plus a
  SHA-256 over the tracked binary diff and sorted untracked path/content pairs. Freeze these into
  `SourceProvenance`; issue 08 still requires a clean tree.
- Include an example plan in CLI help or `docs/`, using generation 7 versus
  `ValueFunctionPlayer`, four search simulations, no exploration, randomized legal boards, and a
  small explicit game count.

## Run behavior

- Open/freeze the store, compute the schedule, and submit only pending games.
- `--workers` defaults conservatively and must be at least one.
- Each worker receives serializable `ScheduledGame` data and returns one result/failure; workers do
  not write shared files.
- The parent process writes each result atomically as it arrives.
- Ctrl-C stops submitting/collecting cleanly; completed files remain resumable.
- Progress names completed/scheduled games, failures, elapsed time, and output directory.
- A first `TechnicalFailure` is retried once. A second attempt becomes terminal; deterministic
  failures cannot retry forever.
- Exit nonzero on plan mismatch, invalid model hashes, infrastructure errors, or any terminal
  technical game failure. Dropped games are summarized but do not by themselves make `run`
  nonzero.
- Never retrain, calibrate, adopt, or modify a model.

## Report behavior

- `report` loads the frozen plan and valid completed results, then calls the pure summarizer.
- It prints Markdown to stdout by default.
- Optional JSON/Markdown outputs are deterministic and written atomically.
- It clearly labels incomplete experiments.
- It does no game execution and succeeds without Catanatron model loading when artifacts are valid.

## Tests

- Invalid/unknown plan fields and relative path resolution.
- Tiny run creates plan and game artifacts; rerun performs zero games.
- Simulated interruption leaves completed games and resumes the rest.
- `--workers 1` and `--workers 2` produce identical deterministic result documents.
- Report reads fixtures without playing and labels incomplete results.
- Changed model/sidecar refuses resume.
- Clean and dirty source provenance are frozen correctly; changing source commit/diff refuses
  resume.
- First failure retries once, second failure is terminal, and exit codes follow the declared table.
- CLI exit codes and stderr messages are useful and contain no traceback for user errors.
- Full smoke test uses very few reduced-target games and is marked `engine`.

## Non-goals

- A web interface.
- Editing plans after an experiment starts.
- Automatically choosing sample size from observed results.
- Running the large published audit in CI.
- Comparing Intervention variants.

## Handoff

Provide the exact example plan, commands, artifact paths, worker behavior, and exit-code table.
Update README only with the stable user-facing commands; keep research interpretation out of it.
